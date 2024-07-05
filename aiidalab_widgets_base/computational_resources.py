from __future__ import annotations

import copy
import enum
import re
import subprocess
import threading
from collections import namedtuple
from pathlib import Path
from uuid import UUID

import ipywidgets as ipw
import jinja2
import pexpect
import shortuuid
import traitlets as tl
from aiida import common, orm, plugins
from aiida.orm.utils.builders.computer import ComputerBuilder
from aiida.transports.plugins import ssh as aiida_ssh_plugin
from humanfriendly import InvalidSize, parse_size
from IPython.display import clear_output, display
from jinja2 import meta as jinja2_meta

from .databases import ComputationalResourcesDatabaseWidget
from .utils import MessageLevel, StatusHTML, wrap_message

STYLE = {"description_width": "180px"}
LAYOUT = {"width": "400px"}


class ComputationalResourcesWidget(ipw.VBox):
    """Code selection widget.
    Attributes:

    value(code UUID): Trait that points to the selected UUID of the code instance.
    It can be set either to an AiiDA code UUID or to a code label.
    It is linked to the `value` trait of the `self.code_select_dropdown` widget.

    codes(Dict): Trait that contains a dictionary (label => Code UUID) for all
    codes found in the AiiDA database for the selected plugin. It is linked
    to the 'options' trait of the `self.code_select_dropdown` widget.

    allow_hidden_codes(Bool): Trait that defines whether to show hidden codes or not.

    allow_disabled_computers(Bool): Trait that defines whether to show codes on disabled
    computers.
    """

    value = tl.Unicode(allow_none=True)
    codes = tl.Dict(allow_none=True)
    allow_hidden_codes = tl.Bool(False)
    allow_disabled_computers = tl.Bool(False)

    # code output layout width
    _output_width = "460px"

    def __init__(
        self,
        description="Select code:",
        enable_quick_setup=True,
        enable_detailed_setup=True,
        clear_after=None,
        default_calc_job_plugin=None,
        **kwargs,
    ):
        """Dropdown for Codes for one input plugin.

        description (str): Description to display before the dropdown.
        """
        clear_after = clear_after or 15
        self.default_calc_job_plugin = default_calc_job_plugin
        self.output = ipw.HTML()
        self.setup_message = StatusHTML(clear_after=clear_after)
        self.code_select_dropdown = ipw.Dropdown(
            description=description,
            disabled=True,
            value=None,
            style={"description_width": "initial"},
        )

        # Create bi-directional link between the code_select_dropdown and the codes trait.
        tl.directional_link(
            (self, "codes"),
            (self.code_select_dropdown, "options"),
            transform=lambda x: [(key, x[key]) for key in x],
        )
        tl.directional_link(
            (self.code_select_dropdown, "options"),
            (self, "codes"),
            transform=lambda x: {c[0]: c[1] for c in x},
        )
        tl.link((self.code_select_dropdown, "value"), (self, "value"))

        self.observe(
            self.refresh, names=["allow_disabled_computers", "allow_hidden_codes"]
        )

        self.btn_setup_new_code = ipw.ToggleButton(description="Setup new code")
        self.btn_setup_new_code.observe(self._setup_new_code, "value")

        self._setup_new_code_output = ipw.Output(layout={"width": self._output_width})

        self._default_user_email = orm.User.collection.get_default().email

        children = [
            ipw.HBox([self.code_select_dropdown, self.btn_setup_new_code]),
            self._setup_new_code_output,
            self.output,
        ]
        super().__init__(children=children, **kwargs)

        # Computer/code setup
        self.resource_setup = _ResourceSetupBaseWidget(
            default_calc_job_plugin=self.default_calc_job_plugin,
            enable_quick_setup=enable_quick_setup,
            enable_detailed_setup=enable_detailed_setup,
        )
        self.resource_setup.observe(self.refresh, "success")
        tl.dlink(
            (self.resource_setup, "message"),
            (self.setup_message, "message"),
        )

        self.refresh()

    def _get_codes(self):
        """Query the list of available codes."""
        user = orm.User.collection.get(email=self._default_user_email)

        filters = (
            {"attributes.input_plugin": self.default_calc_job_plugin}
            if self.default_calc_job_plugin
            else {}
        )

        return [
            (self._full_code_label(c[0]), c[0].uuid)
            for c in orm.QueryBuilder()
            .append(
                orm.Code,
                filters=filters,
            )
            .all()
            if c[0].computer.is_user_configured(user)
            and (self.allow_hidden_codes or not c[0].is_hidden)
            and (self.allow_disabled_computers or c[0].computer.is_user_enabled(user))
        ]

    @staticmethod
    def _full_code_label(code):
        return f"{code.label}@{code.computer.label}"

    def refresh(self, _=None):
        """Refresh available codes.

        The job of this function is to look in AiiDA database, find available codes and
        put them in the code_select_dropdown widget."""
        self.output.value = ""

        with self.hold_trait_notifications():
            self.code_select_dropdown.options = self._get_codes()
            if not self.code_select_dropdown.options:
                self.output.value = f"No codes found for default calcjob plugin {self.default_calc_job_plugin!r}."
                self.code_select_dropdown.disabled = True
            else:
                self.code_select_dropdown.disabled = False
            self.code_select_dropdown.value = None

    @tl.validate("value")
    def _validate_value(self, change):
        """Check if the code is valid in DB"""
        code_uuid = change["value"]
        self.output.value = ""

        # If code None, set value to None.
        if code_uuid is None:
            return None

        try:
            _ = UUID(code_uuid, version=4)
        except ValueError:
            self.output.value = f"""'<span style="color:red">{code_uuid}</span>'
            is not a valid UUID."""
        else:
            return code_uuid

    def _setup_new_code(self, _=None):
        with self._setup_new_code_output:
            clear_output()
            if self.btn_setup_new_code.value:
                self._setup_new_code_output.layout = {
                    "width": self._output_width,
                    "border": "1px solid gray",
                }

                children = [
                    self.resource_setup,
                    self.setup_message,
                ]
                display(*children)
            else:
                self._setup_new_code_output.layout = {
                    "width": self._output_width,
                    "border": "none",
                }


class SshConnectionState(enum.Enum):
    waiting_for_input = -1
    enter_password = 0
    success = 1
    keys_already_present = 2
    do_you_want_to_continue = 3
    no_keys = 4
    unknown_hostname = 5
    connection_refused = 6
    end_of_file = 7


class SshComputerSetup(ipw.VBox):
    """Setup a passwordless access to a computer."""

    ssh_config = tl.Dict()
    ssh_connection_state = tl.UseEnum(
        SshConnectionState, allow_none=True, default_value=None
    )
    SSH_POSSIBLE_RESPONSES = [
        # order matters! the index will return by pexpect and compare
        # with SshConnectionState
        "[Pp]assword:",  # 0
        "Now try logging into",  # 1
        "All keys were skipped because they already exist on the remote system",  # 2
        "Are you sure you want to continue connecting (yes/no)?",  # 3
        "ERROR: No identities found",  # 4
        "Could not resolve hostname",  # 5
        "Connection refused",  # 6
        pexpect.EOF,  # 7
    ]
    message = tl.Unicode()
    password_message = tl.Unicode("The passwordless enabling log.")

    def __init__(self, ssh_folder: Path | None = None, **kwargs):
        """Setup a passwordless access to a computer."""
        # ssh folder init
        if ssh_folder is None:
            ssh_folder = Path.home() / ".ssh"

        if not ssh_folder.exists():
            ssh_folder.mkdir()
            ssh_folder.chmod(0o700)

        self._ssh_folder = ssh_folder

        self._ssh_connection_message = None
        self._password_message = ipw.HTML()
        tl.dlink(
            (self, "password_message"),
            (self._password_message, "value"),
            transform=lambda x: f"<b>SSH log: {x}</b>",
        )
        self._ssh_password = ipw.Password(
            description="password:",
            disabled=False,
            layout=LAYOUT,
            style=STYLE,
        )
        # Don't show the continue button until it ask for password the
        # second time, which happened when the proxy jump is set. The
        # first time it ask for password is for the jump host.
        self._continue_with_password_button = ipw.Button(
            description="Continue",
            layout={"width": "100px", "display": "none"},
        )
        self._continue_with_password_button.on_click(self._send_password)

        self.password_box = ipw.VBox(
            [
                ipw.HBox([self._ssh_password, self._continue_with_password_button]),
                self._password_message,
            ]
        )

        # Username.
        self.username = ipw.Text(description="Username:", layout=LAYOUT, style=STYLE)

        # Port.
        self.port = ipw.IntText(
            description="Port:",
            value=22,
            layout=LAYOUT,
            style=STYLE,
        )

        # Hostname.
        self.hostname = ipw.Text(
            description="Computer hostname:",
            layout=LAYOUT,
            style=STYLE,
        )

        # ProxyJump.
        self.proxy_jump = ipw.Text(
            description="ProxyJump:",
            layout=LAYOUT,
            style=STYLE,
        )
        # ProxyJump.
        self.proxy_command = ipw.Text(
            description="ProxyCommand:",
            layout=LAYOUT,
            style=STYLE,
        )

        self._inp_private_key = ipw.FileUpload(
            accept="",
            layout=LAYOUT,
            description="Private key",
            multiple=False,
        )
        self._verification_mode = ipw.Dropdown(
            options=[
                ("Password", "password"),
                ("Use custom private key", "private_key"),
                ("Download public key", "public_key"),
                ("Multiple factor authentication", "mfa"),
            ],
            layout=LAYOUT,
            style=STYLE,
            value="password",
            description="Verification mode:",
            disabled=False,
        )
        self._verification_mode.observe(
            self._on_verification_mode_change, names="value"
        )
        self._verification_mode_output = ipw.Output()

        self._continue_button = ipw.ToggleButton(
            description="Continue", layout={"width": "100px"}, value=False
        )

        # Setup ssh button and output.
        btn_setup_ssh = ipw.Button(description="Setup ssh")
        btn_setup_ssh.on_click(self._on_setup_ssh_button_pressed)

        children = [
            self.hostname,
            self.port,
            self.username,
            self.proxy_jump,
            self.proxy_command,
            self._verification_mode,
            self._verification_mode_output,
            btn_setup_ssh,
        ]
        super().__init__(children, **kwargs)

    def _ssh_keygen(self):
        """Generate ssh key pair."""
        self.message = wrap_message(
            "Generating SSH key pair.",
            MessageLevel.SUCCESS,
        )
        fpath = self._ssh_folder / "id_rsa"
        keygen_cmd = [
            "ssh-keygen",
            "-f",
            fpath,
            "-t",
            "rsa",
            "-b",
            "4096",
            "-m",
            "PEM",
            "-N",
            "",
        ]
        if not fpath.exists():
            subprocess.run(keygen_cmd, capture_output=True, check=True)

    def _can_login(self):
        """Check if it is possible to login into the remote host."""
        # With BatchMode on, no password prompt or other interaction is attempted,
        # so a connect that requires a password will fail.
        ret = subprocess.call(
            [
                "ssh",
                self.hostname.value,
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                "true",
            ]
        )
        return ret == 0

    def _is_in_config(self):
        """Check if the SSH config file contains host information."""
        config_path = self._ssh_folder / "config"
        if not config_path.exists():
            return False
        sshcfg = aiida_ssh_plugin.parse_sshconfig(self.hostname.value)
        # NOTE: parse_sshconfig returns a dict with a hostname
        # even if it is not in the config file.
        # We require at least the user to be specified.
        if "user" not in sshcfg:
            return False
        return True

    def _write_ssh_config(self, private_key_abs_fname=None):
        """Put host information into the config file."""
        config_path = self._ssh_folder / "config"

        self.message = wrap_message(
            f"Adding {self.hostname.value} section to {config_path}",
            MessageLevel.SUCCESS,
        )
        with open(config_path, "a") as file:
            file.write(f"Host {self.hostname.value}\n")
            file.write(f"  User {self.username.value}\n")
            file.write(f"  Port {self.port.value}\n")
            if self.proxy_jump.value != "":
                file.write(
                    f"  ProxyJump {self.proxy_jump.value.format(username=self.username.value)}\n"
                )
            if self.proxy_command.value != "":
                file.write(
                    f"  ProxyCommand {self.proxy_command.value.format(username=self.username.value)}\n"
                )
            if private_key_abs_fname:
                file.write(f"  IdentityFile {private_key_abs_fname}\n")
            file.write("  ServerAliveInterval 5\n")

    def key_pair_prepare(self):
        """Prepare key pair for the ssh connection."""
        # Always start by generating a key pair if they are not present.
        self._ssh_keygen()

        # If hostname & username are not provided - do not do anything.
        if self.hostname.value == "":  # check hostname
            message = "Please specify the computer name (for SSH)"

            raise ValueError(message)

        if self.username.value == "":  # check username
            message = "Please specify your SSH username."

            raise ValueError(message)

    def thread_ssh_copy_id(self):
        """Copy public key on the remote computer, on a separate thread."""
        ssh_connection_thread = threading.Thread(target=self._ssh_copy_id)
        ssh_connection_thread.start()

    def _on_setup_ssh_button_pressed(self, _=None):
        """Setup ssh connection."""
        if self._verification_mode.value == "password":
            try:
                self.key_pair_prepare()

            except ValueError as exc:
                self.message = wrap_message(str(exc), MessageLevel.ERROR)
                return

            self.thread_ssh_copy_id()

        # For not password ssh auth (such as using private_key or 2FA), key pair is not needed (2FA)
        # or the key pair is ready.
        # There are other mechanism to set up the ssh connection.
        # But we still need to write the ssh config to the ssh config file for such as
        # proxy jump.

        private_key_fname = None
        if self._verification_mode.value == "private_key":
            # Write private key in ~/.ssh/ and use the name of upload file,
            # if exist, generate random string and append to filename then override current name.

            # unwrap private key file and setting temporary private_key content
            private_key_fname, private_key_content = self._private_key
            if private_key_fname is None:  # check private key file
                message = "Please upload your private key file."
                self.message = wrap_message(message, MessageLevel.ERROR)
                return

            filename = Path(private_key_fname).name

            # if the private key filename is exist, generate random string and append to filename subfix
            # then override current name.
            if filename in [str(p.name) for p in Path(self._ssh_folder).iterdir()]:
                private_key_fpath = self._ssh_folder / f"{filename}-{shortuuid.uuid()}"

            self._add_private_key(private_key_fpath, private_key_content)

        # TODO(danielhollas): I am not sure this is correct. What if the user wants
        # to overwrite the private key? Or any other config? The configuration would never be written.
        # And the user is not notified that we did not write anything.
        # https://github.com/aiidalab/aiidalab-widgets-base/issues/516
        if not self._is_in_config():
            self._write_ssh_config(private_key_abs_fname=private_key_fname)

    def _ssh_copy_id(self):
        """Run the ssh-copy-id command and follow it until it is completed."""
        timeout = 10
        self.password_message = f"Sending public key to {self.hostname.value}... "
        self._ssh_connection_process = pexpect.spawn(
            f"ssh-copy-id {self.hostname.value}"
        )
        while True:
            try:
                idx = self._ssh_connection_process.expect(
                    self.SSH_POSSIBLE_RESPONSES,
                    timeout=timeout,
                )
                self.ssh_connection_state = SshConnectionState(idx)
            except pexpect.TIMEOUT:
                self.password_message = f"Exceeded {timeout} s timeout. Please check you username and password and try again."
                break

            # Terminating the process when nothing else can be done.
            if self.ssh_connection_state in (
                SshConnectionState.success,
                SshConnectionState.keys_already_present,
                SshConnectionState.no_keys,
                SshConnectionState.unknown_hostname,
                SshConnectionState.connection_refused,
                SshConnectionState.end_of_file,
            ):
                break

        self._ssh_connection_message = None
        self._ssh_connection_process = None

    def _send_password(self, _=None):
        self._continue_with_password_button.disabled = True
        self._ssh_connection_process.sendline(self._ssh_password.value)

    @tl.observe("ssh_connection_state")
    def _observe_ssh_connnection_state(self, _=None):
        """Observe the ssh connection state and act according to the changes."""
        if self.ssh_connection_state is SshConnectionState.waiting_for_input:
            return
        if self.ssh_connection_state is SshConnectionState.success:
            self.password_message = (
                "The passwordless connection has been set up successfully."
            )
            return
        if self.ssh_connection_state is SshConnectionState.keys_already_present:
            self.password_message = "The passwordless connection has already been setup. Nothing to be done."
            return
        if self.ssh_connection_state is SshConnectionState.no_keys:
            self.password_message = (
                " Failed\nLooks like the key pair is not present in ~/.ssh folder."
            )
            return
        if self.ssh_connection_state is SshConnectionState.unknown_hostname:
            self.password_message = "Failed\nUnknown hostname."
            return
        if self.ssh_connection_state is SshConnectionState.connection_refused:
            self.password_message = "Failed\nConnection refused."
            return
        if self.ssh_connection_state is SshConnectionState.end_of_file:
            self.password_message = (
                "Didn't manage to connect. Please check your username/password."
            )
            return
        if self.ssh_connection_state is SshConnectionState.enter_password:
            self._handle_ssh_password()
        elif self.ssh_connection_state is SshConnectionState.do_you_want_to_continue:
            self._ssh_connection_process.sendline("yes")

    def _handle_ssh_password(self):
        """Send a password to a remote computer."""
        message = (
            self._ssh_connection_process.before.splitlines()[-1]
            + self._ssh_connection_process.after
        )
        if self._ssh_connection_message == message:
            self._ssh_connection_process.sendline(self._ssh_password.value)
        else:
            self.password_message = (
                f"Please enter {self.username.value}@{self.hostname.value}'s password:"
                if message == b"Password:"
                else f"Please enter {message.decode('utf-8')}"
            )
            self._ssh_password.disabled = False
            self._continue_with_password_button.disabled = False
            self._ssh_connection_message = message

        # If user did not provide a password, we wait for the input.
        # Otherwise, we send the password.
        if self._ssh_password.value == "":
            self.ssh_connection_state = SshConnectionState.waiting_for_input
        else:
            self.password_message = 'Sending password <i class="fa fa-spinner" aria-hidden="true"></i> (timeout 10s)'
            self._send_password()

    def _on_verification_mode_change(self, change):
        """which verification mode is chosen."""
        with self._verification_mode_output:
            clear_output()
            if self._verification_mode.value == "private_key":
                display(self._inp_private_key)
            elif self._verification_mode.value == "public_key":
                public_key = self._ssh_folder / "id_rsa.pub"
                if public_key.exists():
                    display(
                        ipw.HTML(
                            f"""<pre style="background-color: #253239; color: #cdd3df; line-height: normal; custom=test">{public_key.read_text()}</pre>""",
                            layout={"width": "100%"},
                        )
                    )

    @property
    def _private_key(self) -> tuple[str | None, bytes | None]:
        """Unwrap private key file and setting filename and file content."""
        if self._inp_private_key.value:
            (fname, _value), *_ = self._inp_private_key.value.items()
            content = copy.copy(_value["content"])
            self._inp_private_key.value.clear()
            self._inp_private_key._counter = 0  # pylint: disable=protected-access
            return fname, content
        return None, None

    @staticmethod
    def _add_private_key(private_key_fpath: Path, private_key_content: bytes):
        """Write private key to the private key file in the ssh folder."""
        private_key_fpath.write_bytes(private_key_content)
        private_key_fpath.chmod(0o600)

    def _reset(self):
        self.hostname.value = ""
        self.port.value = 22
        self.username.value = ""
        self.proxy_jump.value = ""
        self.proxy_command.value = ""

    @tl.observe("ssh_config")
    def _observe_ssh_config(self, change):
        """Pre-filling the input fields."""
        self._reset()

        new_ssh_config = change["new"]
        if "hostname" in new_ssh_config:
            self.hostname.value = new_ssh_config["hostname"]
        if "username" in new_ssh_config:
            self.username.value = new_ssh_config["username"]
        if "port" in new_ssh_config:
            self.port.value = int(new_ssh_config["port"])
        if "proxy_jump" in new_ssh_config:
            self.proxy_jump.value = new_ssh_config["proxy_jump"]
        if "proxy_command" in new_ssh_config:
            self.proxy_command.value = new_ssh_config["proxy_command"]


class AiidaComputerSetup(ipw.VBox):
    """Inform AiiDA about a computer."""

    computer_setup = tl.Dict(allow_none=True)
    computer_configure = tl.Dict(allow_none=True)
    message = tl.Unicode()

    def __init__(self, **kwargs):
        self._on_setup_computer_success = []
        self._default_user_email = orm.User.collection.get_default().email

        # List of widgets to be displayed.
        self.label = ipw.Text(
            value="",
            placeholder="Will only be used within AiiDA",
            description="Computer name:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Hostname.
        self.hostname = ipw.Text(description="Hostname:", layout=LAYOUT, style=STYLE)

        # Computer description.
        self.description = ipw.Text(
            value="",
            placeholder="No description (yet)",
            description="Computer description:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Directory where to run the simulations.
        self.work_dir = ipw.Text(
            value="",
            placeholder="/home/{username}/aiida_run",
            description="AiiDA working directory:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Mpirun command.
        self.mpirun_command = ipw.Text(
            value="mpirun -n {tot_num_mpiprocs}",
            description="Mpirun command:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Number of CPUs per node.
        self.mpiprocs_per_machine = ipw.IntText(
            value=1,
            step=1,
            description="#CPU(s) per node:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Memory per node.
        self.default_memory_per_machine_widget = ipw.Text(
            value="",
            placeholder="not specified",
            description="Memory per node:",
            layout=LAYOUT,
            style=STYLE,
        )
        memory_wrong_syntax = ipw.HTML(
            value="""<i class="fa fa-times" style="color:red;font-size:2em;" ></i> wrong syntax""",
        )
        memory_wrong_syntax.layout.display = "none"
        self.default_memory_per_machine = None

        def observe_memory_per_machine(change):
            """Check if the string defining memory is valid."""
            memory_wrong_syntax.layout.display = "none"
            if not self.default_memory_per_machine_widget.value:
                self.default_memory_per_machine = None
                return
            try:
                self.default_memory_per_machine = (
                    int(parse_size(change["new"], binary=True) / 1024) or None
                )
                memory_wrong_syntax.layout.display = "none"
            except InvalidSize:
                memory_wrong_syntax.layout.display = "block"
                self.default_memory_per_machine = None

        self.default_memory_per_machine_widget.observe(
            observe_memory_per_machine, names="value"
        )

        # Transport type.
        self.transport = ipw.Dropdown(
            value="core.local",
            options=plugins.entry_point.get_entry_point_names("aiida.transports"),
            description="Transport type:",
            style=STYLE,
        )

        # Safe interval.
        self.safe_interval = ipw.FloatText(
            value=30.0,
            description="Min. connection interval (sec):",
            layout=LAYOUT,
            style=STYLE,
        )

        # Scheduler.
        self.scheduler = ipw.Dropdown(
            value="core.slurm",
            options=plugins.entry_point.get_entry_point_names("aiida.schedulers"),
            description="Scheduler:",
            style=STYLE,
        )

        self.shebang = ipw.Text(
            value="#!/usr/bin/env bash",
            description="Shebang:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Use double quotes to escape.
        self.use_double_quotes = ipw.Checkbox(
            value=False,
            description="Use double quotes to escape environment variable of job script.",
        )

        # Use login shell.
        self.use_login_shell = ipw.Checkbox(value=True, description="Use login shell")

        # Prepend text.
        self.prepend_text = ipw.Textarea(
            placeholder="Text to prepend to each command execution",
            description="Prepend text:",
            layout=LAYOUT,
        )

        # Append text.
        self.append_text = ipw.Textarea(
            placeholder="Text to append to each command execution",
            description="Append text:",
            layout=LAYOUT,
        )

        # Buttons and outputs.
        self.setup_button = ipw.Button(description="Setup computer")
        self.setup_button.on_click(self.on_setup_computer)
        test_button = ipw.Button(description="Test computer")
        test_button.on_click(self.test)
        self._test_out = ipw.HTML(layout=LAYOUT)

        # Organize the widgets
        children = [
            self.label,
            self.hostname,
            self.description,
            self.work_dir,
            self.mpirun_command,
            self.mpiprocs_per_machine,
            ipw.HBox([self.default_memory_per_machine_widget, memory_wrong_syntax]),
            self.transport,
            self.safe_interval,
            self.scheduler,
            self.shebang,
            self.use_login_shell,
            self.use_double_quotes,
            self.prepend_text,
            self.append_text,
            self.setup_button,
            test_button,
            self._test_out,
        ]

        super().__init__(children, **kwargs)

    def _configure_computer(self, computer: orm.Computer, transport: str):
        # Use default AiiDA user
        user = orm.User.collection.get(email=self._default_user_email)
        if transport == "core.ssh":
            self._configure_computer_ssh(computer, user)
        elif transport == "core.local":
            self._configure_computer_local(computer, user)
        else:
            msg = f"invalid transport type '{transport}'"
            raise common.ValidationError(msg)

    def _configure_computer_ssh(self, computer: orm.Computer, user: orm.User):
        """Configure the computer with SSH transport

        There are three sources of authparams information ordered by priority increase:
        - the default values
        - the SSH config file
        - the computer_configure dictionary

        At the moment, there is no overlap between the SSH config file and the computer_configure dictionary.

        The proxyjump and proxycommend can be read from both the SSH config file and the computer_configure dictionary,
        since the SSH config file is generated from the computer_configure dictionary in `SshComputerSetup._write_ssh_config`.
        """
        sshcfg = aiida_ssh_plugin.parse_sshconfig(self.hostname.value)
        authparams = {
            "port": int(sshcfg.get("port", 22)),
            "look_for_keys": True,
            "key_filename": str(
                Path(sshcfg.get("identityfile", ["~/.ssh/id_rsa"])[0]).expanduser()
            ),
            "timeout": 60,
            "allow_agent": True,
            "proxy_jump": "",
            "proxy_command": "",
            "compress": True,
            "gss_auth": False,
            "gss_kex": False,
            "gss_deleg_creds": False,
            "gss_host": self.hostname.value,
            "load_system_host_keys": True,
            "key_policy": "WarningPolicy",
            "use_login_shell": self.use_login_shell.value,
            "safe_interval": self.safe_interval.value,
        }
        if "username" in self.computer_configure:
            authparams["username"] = self.computer_configure["username"]
        else:
            try:
                # This require the Ssh connection setup is done before the computer setup
                authparams["username"] = sshcfg["user"]
            except KeyError as exc:
                message = "SSH username is not provided"
                raise RuntimeError(message) from exc

        if "proxy_jump" in self.computer_configure:
            authparams["proxy_jump"] = self.computer_configure["proxy_jump"]

        if "proxy_command" in self.computer_configure:
            authparams["proxy_command"] = self.computer_configure["proxy_command"]

        if "key_filename" in self.computer_configure:
            authparams["key_filename"] = str(
                Path(self.computer_configure["key_filename"]).expanduser()
            )

        if "key_policy" in self.computer_configure:
            authparams["key_policy"] = self.computer_configure["key_policy"]

        computer.configure(user=user, **authparams)
        return True

    def _configure_computer_local(self, computer: orm.Computer, user: orm.User):
        """Configure the computer with local transport"""
        authparams = {
            "use_login_shell": self.use_login_shell.value,
            "safe_interval": self.safe_interval.value,
        }
        computer.configure(user=user, **authparams)
        return True

    def _run_callbacks_if_computer_exists(self, label):
        """Run things on an existing computer"""
        if self._computer_exists(label):
            for function in self._on_setup_computer_success:
                function()
            return True
        return False

    def _computer_exists(self, label):
        try:
            orm.load_computer(label=label)
        except common.NotExistent:
            return False
        return True

    def _validate_computer_settings(self):
        if self.label.value == "":  # check computer label
            self.message = wrap_message(
                "Please specify the computer name (for AiiDA)",
                MessageLevel.WARNING,
            )
            return False

        if self.work_dir.value == "":
            self.message = wrap_message(
                "Please specify working directory",
                MessageLevel.WARNING,
            )
            return False

        if self.hostname.value == "":
            self.message = wrap_message(
                "Please specify hostname",
                MessageLevel.WARNING,
            )
            return False

        return True

    def on_setup_computer(self, _=None):
        """Create a new computer."""
        if not self._validate_computer_settings():
            return False

        # If the computer already exists, we just run the registered functions and return
        if self._run_callbacks_if_computer_exists(self.label.value):
            self.message = wrap_message(
                f"A computer {self.label.value} already exists. Skipping creation.",
                MessageLevel.INFO,
            )
            return True

        items_to_configure = [
            "label",
            "hostname",
            "description",
            "work_dir",
            "mpirun_command",
            "mpiprocs_per_machine",
            "transport",
            "use_double_quotes",
            "scheduler",
            "prepend_text",
            "append_text",
            "shebang",
        ]

        kwargs = {key: getattr(self, key).value for key in items_to_configure}

        computer_builder = ComputerBuilder(
            default_memory_per_machine=self.default_memory_per_machine, **kwargs
        )
        try:
            computer = computer_builder.new()
            self._configure_computer(computer, self.transport.value)
            computer.store()
        except (
            ComputerBuilder.ComputerValidationError,
            common.exceptions.ValidationError,
            RuntimeError,
        ) as err:
            self.message = wrap_message(
                f"Computer setup failed! {type(err).__name__}: {err}",
                MessageLevel.ERROR,
            )
            return False

        # Callbacks will not run if the computer is not stored
        if self._run_callbacks_if_computer_exists(self.label.value):
            self.message = wrap_message(
                f"Computer<{computer.pk}> {computer.label} created",
                MessageLevel.SUCCESS,
            )
            return True

        self.message = wrap_message(
            f"Failed to create computer {computer.label}",
            MessageLevel.ERROR,
        )
        return False

    def on_setup_computer_success(self, function):
        self._on_setup_computer_success.append(function)

    def test(self, _=None):
        if self.label.value == "":
            self._test_out.value = "Please specify the computer name (for AiiDA)."
            return False
        elif not self._computer_exists(self.label.value):
            self._test_out.value = (
                f"A computer called <b>{self.label.value}</b> does not exist."
            )
            return False

        self._test_out.value = '<i class="fa fa-spinner fa-pulse"></i>'
        process_result = subprocess.run(
            ["verdi", "computer", "test", "--print-traceback", self.label.value],
            capture_output=True,
            check=False,
        )

        if process_result.returncode == 0:
            self._test_out.value = process_result.stdout.decode("utf-8").replace(
                "\n", "<br>"
            )
            return True
        else:
            self._test_out.value = process_result.stderr.decode("utf-8").replace(
                "\n", "<br>"
            )
            return False

    def _reset(self):
        self.label.value = ""
        self.hostname.value = ""
        self.description.value = ""
        self.work_dir.value = ""
        self.mpirun_command.value = "mpirun -n {tot_num_mpiprocs}"
        self.default_memory_per_machine_widget.value = ""
        self.mpiprocs_per_machine.value = 1
        self.transport.value = "core.ssh"
        self.safe_interval.value = 30.0
        self.scheduler.value = "core.slurm"
        self.shebang.value = "#!/usr/bin/env bash"
        self.use_login_shell.value = True
        self.use_double_quotes.value = False
        self.prepend_text.value = ""
        self.append_text.value = ""

    @tl.observe("computer_setup")
    def _observe_computer_setup(self, _=None):
        for key, value in self.computer_setup.items():
            if key == "default_memory_per_machine":
                self.default_memory_per_machine_widget.value = f"{value} KB"
            elif hasattr(self, key):
                getattr(self, key).value = value

    @tl.observe("computer_configure")
    def _observe_computer_configure(self, _=None):
        for key, value in self.computer_configure.items():
            if hasattr(self, key):
                getattr(self, key).value = value

    @tl.observe("computer_setup", "computer_configure")
    def _observe_computer_setup_and_configure(self, _=None):
        if not self.some_values_provided:
            self._reset()

    @property
    def some_values_provided(self):
        return any((self.computer_setup, self.computer_configure))

    @property
    def all_values_provided(self):
        return all((self.computer_setup, self.computer_configure))


class AiidaCodeSetup(ipw.VBox):
    """Class that allows to setup AiiDA code"""

    code_setup = tl.Dict(allow_none=True)
    message = tl.Unicode()

    def __init__(self, **kwargs):
        self._on_setup_code_success = []

        # Code label.
        self.label = ipw.Text(
            description="AiiDA code label:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Computer on which the code is installed. The value of this widget is
        # the UUID of the selected computer.
        self.computer = ComputerDropdownWidget()

        # Code plugin.
        self.default_calc_job_plugin = ipw.Dropdown(
            options=sorted(
                (ep.name, ep.name)
                for ep in plugins.entry_point.get_entry_points("aiida.calculations")
            ),
            description="Code plugin:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Code description.
        self.description = ipw.Text(
            placeholder="No description (yet)",
            description="Code description:",
            layout=LAYOUT,
            style=STYLE,
        )

        self.filepath_executable = ipw.Text(
            placeholder="/path/to/executable",
            description="Absolute path to executable:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Use double quotes to escape.
        self.use_double_quotes = ipw.Checkbox(
            value=False,
            description="Use double quotes to escape environment variable of job script.",
        )

        self.prepend_text = ipw.Textarea(
            placeholder="Text to prepend to each command execution",
            description="Prepend text:",
            layout=LAYOUT,
        )

        self.append_text = ipw.Textarea(
            placeholder="Text to append to each command execution",
            description="Append text:",
            layout=LAYOUT,
        )

        btn_setup_code = ipw.Button(description="Setup code")
        btn_setup_code.on_click(self.on_setup_code)
        self.setup_code_out = ipw.Output()

        children = [
            self.label,
            self.computer,
            self.default_calc_job_plugin,
            self.description,
            self.filepath_executable,
            self.use_double_quotes,
            self.prepend_text,
            self.append_text,
            btn_setup_code,
            self.setup_code_out,
        ]
        super().__init__(children, **kwargs)

    @tl.validate("default_calc_job_plugin")
    def _validate_default_calc_job_plugin(self, proposal):
        plugin = proposal["value"]
        return plugin if plugin in self.default_calc_job_plugin.options else None

    def on_setup_code(self, _=None):
        """Setup an AiiDA code."""
        with self.setup_code_out:
            clear_output()

            if not self.computer.value:
                self.message = wrap_message(
                    "Please select an existing computer.",
                    MessageLevel.WARNING,
                )
                return False

            items_to_configure = [
                "label",
                "description",
                "default_calc_job_plugin",
                "filepath_executable",
                "use_double_quotes",
                "prepend_text",
                "append_text",
            ]

            containerized_code_additional_items = [
                "image_name",
                "engine_command",
            ]

            kwargs = {key: getattr(self, key).value for key in items_to_configure}

            # Check for additional keys needed for orm.ContainerizedCode
            for container_key in containerized_code_additional_items:
                if container_key in self.code_setup.keys():
                    kwargs[container_key] = self.code_setup[container_key]

            # set computer from its widget value the UUID of the computer.
            computer = orm.load_computer(self.computer.value)

            # Checking if the code with this name already exists
            qb = orm.QueryBuilder()
            qb.append(orm.Computer, filters={"uuid": computer.uuid}, tag="computer")
            qb.append(
                orm.AbstractCode,
                with_computer="computer",
                filters={"label": kwargs["label"]},
            )
            if qb.count() > 0:
                self.message = wrap_message(
                    f"Code {kwargs['label']}@{computer.label} already exists, skipping creation.",
                    MessageLevel.INFO,
                )
                # TODO: (unkcpz) as callback function this return value not actually used
                # meanwhile if the code already exists we still want to regard it as success (TBD).
                # and the `_on_setup_code_success` callback functions will run.
                # The return will break the flow and handle back the control to the caller.
                # The proper way is to not return but raise an exception and handle it in the caller function
                # for the afterward process.
                return False

            try:
                if "image_name" in kwargs.keys():
                    code = orm.ContainerizedCode(computer=computer, **kwargs)
                else:
                    code = orm.InstalledCode(computer=computer, **kwargs)
            except (common.exceptions.InputValidationError, KeyError) as exception:
                self.message = wrap_message(
                    f"Invalid input for code creation: <code>{exception}</code>",
                    MessageLevel.ERROR,
                )
                return False

            try:
                code.store()
                code.is_hidden = False
            except common.exceptions.ValidationError as exception:
                self.message = wrap_message(
                    f"Unable to store the code: <code>{exception}</code>",
                    MessageLevel.ERROR,
                )
                return False

            for function in self._on_setup_code_success:
                function()

            self.message = wrap_message(
                f"Code<{code.pk}> {code.full_label} created",
                MessageLevel.SUCCESS,
            )

            return True

    def on_setup_code_success(self, function):
        self._on_setup_code_success.append(function)

    def _reset(self):
        self.label.value = ""
        self.computer.value = ""
        self.description.value = ""
        self.filepath_executable.value = ""
        self.use_double_quotes.value = False
        self.prepend_text.value = ""
        self.append_text.value = ""

    def refresh(self):
        self._observe_code_setup()

    @tl.observe("code_setup")
    def _observe_code_setup(self, _=None):
        # Setup.
        self.computer.refresh()
        if not self.code_setup:
            self._reset()
        for key, value in self.code_setup.items():
            if hasattr(self, key):
                if key == "default_calc_job_plugin":
                    try:
                        self.default_calc_job_plugin.value = value
                    except tl.TraitError:
                        # If is a template then don't raise the error message.
                        if not re.match(r".*{{.+}}.*", value):
                            self.message = wrap_message(
                                f"Input plugin {value} is not installed.",
                                MessageLevel.WARNING,
                            )
                elif key == "computer":
                    # check if the computer is set by load the label.
                    # if the computer not set put the value to None as placeholder for
                    # ComputerDropdownWidget it will refresh after the computer set up.
                    # if the computer is set pass the UUID to ComputerDropdownWdiget.
                    try:
                        computer = orm.load_computer(value)
                    except common.NotExistent:
                        getattr(self, key).value = None
                    else:
                        getattr(self, key).value = computer.uuid
                else:
                    getattr(self, key).value = value


class ComputerDropdownWidget(ipw.VBox):
    """Widget to select a configured computer.

    Attributes:
        value(computer UUID): Trait that points to the selected Computer instance. It can be set to an AiiDA Computer UUID. It is linked to the 'value' trait of `self._dropdown` widget.
        computers(Dict): Trait that contains a dictionary (label => Computer UUID) for all computers found in the AiiDA database. It is linked to the 'options' trait of `self._dropdown` widget.
        allow_select_disabled(Bool):  Trait that defines whether to show disabled computers.
    """

    value = tl.Unicode(allow_none=True)
    computers = tl.Dict(allow_none=True)
    allow_select_disabled = tl.Bool(False)

    def __init__(self, description="Select computer:", **kwargs):
        """Dropdown for configured AiiDA Computers.

        description (str): Text to display before dropdown.
        """
        self._default_user_email = orm.User.collection.get_default().email

        self.output = ipw.HTML()
        self._dropdown = ipw.Dropdown(
            value=None,
            description=description,
            style=STYLE,
            layout=LAYOUT,
            disabled=True,
        )
        tl.directional_link(
            (self, "computers"),
            (self._dropdown, "options"),
            transform=lambda x: [(key, x[key]) for key in x],
        )
        tl.directional_link(
            (self._dropdown, "options"),
            (self, "computers"),
            transform=lambda x: {c[0]: c[1] for c in x},
        )
        tl.link((self._dropdown, "value"), (self, "value"))

        self.observe(self.refresh, names="allow_select_disabled")

        children = [
            ipw.HBox(
                [
                    self._dropdown,
                ]
            ),
            self.output,
        ]
        self.refresh()
        super().__init__(children=children, **kwargs)

    def _get_computers(self) -> list:
        """Get the list of available computers."""

        # Getting the current user.
        user = orm.User.collection.get(email=self._default_user_email)

        return [
            (c[0].label, c[0].uuid)
            for c in orm.QueryBuilder().append(orm.Computer).all()
            if c[0].is_user_configured(user)
            and (self.allow_select_disabled or c[0].is_user_enabled(user))
        ]

    def refresh(self, _=None):
        """Refresh the list of configured computers."""
        self.output.value = ""
        with self.hold_trait_notifications():
            self._dropdown.options = self._get_computers()
            if not self.computers:
                self.output.value = "No computers found."
                self._dropdown.disabled = True
            else:
                self._dropdown.disabled = False

            self._dropdown.value = None

    @tl.validate("value")
    def _validate_value(self, change):
        """Select computer by computer UUID."""
        computer_uuid = change["value"]
        self.output.value = ""
        if not computer_uuid:
            return None

        try:
            _ = UUID(computer_uuid, version=4)
        except ValueError:
            self.output.value = f"""'<span style="color:red">{computer_uuid}</span>'
            is not a valid UUID."""
        else:
            return computer_uuid

    def select_by_label(self, label):
        """Select computer by computer label."""
        self.output.value = ""
        if not label:
            return None

        try:
            computer_uuid = self.computers[label]
        except KeyError:
            self.output.value = f"""'<span style="color:red">{label}</span>'
            can not find this computer."""
        else:
            self.value = computer_uuid


TemplateVariableLine = namedtuple("TemplateVariableLine", ["key", "str", "vars"])

TemplateVariable = namedtuple("TemplateVariable", ["widget", "lines"])


class TemplateVariablesWidget(ipw.VBox):
    # The input template is a dictionary of keyname and template string.
    templates = tl.Dict(allow_none=True)

    # The output template is a dictionary of keyname and filled string.
    filled_templates = tl.Dict(allow_none=True)

    # the output metadata is a dictionary of keyname and metadata of this template.
    metadata = tl.Dict(allow_none=True)

    def __init__(self):
        # A placeholder for the template variables widget.
        self.template_variables = ipw.VBox()

        # A dictionary of mapping variables.
        # the key is the variable name, and the value is a tuple of (template value and widget).
        self._template_variables = {}
        self._help_text = ipw.HTML(
            """<div>Please fill the template variables below.</div>"""
        )
        self._help_text.layout.display = "none"

        # unfilled_variables is a list of variables that are not filled.
        self.unfilled_variables = []

        super().__init__(
            children=[
                self._help_text,
                self.template_variables,
            ]
        )

    def reset(self):
        """Reset the widget."""
        self.templates = {}
        self.filled_templates = {}
        self._template_variables = {}
        self._help_text.layout.display = "none"
        self.template_variables.children = []

    @tl.observe("templates")
    def _templates_changed(self, _=None):
        """Render the template variables widget."""
        # reset traits and then render the widget.
        self._template_variables = {}
        self.filled_templates = {}
        self._help_text.layout.display = "none"

        self._render()

        self.metadata = self.templates.get("metadata", {})

        # Update the output filled template.
        # After `self._render` all the widgets are created.
        # We can use the widget value to fill the template even not all the widgets are filled.
        self.fill()

    def _render(self):
        """Render the template variables widget."""
        metadata = self.templates.get("metadata", {})
        tooltip = metadata.get("tooltip", None)

        if tooltip:
            self._help_text.value = f"""<div>{tooltip}</div>"""

        for line_key, line_str in self.templates.items():
            env = jinja2.Environment()
            parsed_content = env.parse(line_str)

            # vars is a set of variables in the template
            line_vars = jinja2_meta.find_undeclared_variables(parsed_content)

            # Create a widget for each variable.
            # The var is the name in a template string
            var_metadata = metadata.get("template_variables", {})
            for var in line_vars:
                # one var can be used in multiple templates, so we need to keep track of the mapping with the set of variables.
                var_meta = var_metadata.get(var, {})
                if var in self._template_variables:
                    # use the same widget for the same variable.
                    temp_var = self._template_variables[var]
                    w = temp_var.widget
                    lines = temp_var.lines
                    lines.append(TemplateVariableLine(line_key, line_str, line_vars))
                    template_var = TemplateVariable(w, lines)

                    self._template_variables[var] = template_var
                else:
                    # create a new widget for the variable.
                    description = var_meta.get("key_display", f"{var}")
                    widget_type = var_meta.get("type", "text")
                    if widget_type == "text":
                        w = ipw.Text(
                            description=f"{description}:",
                            value=var_meta.get("default", ""),
                            # delay notifying the observers until the user stops typing
                            continuous_update=False,
                            layout=LAYOUT,
                            style=STYLE,
                        )
                    elif widget_type == "list":
                        w = ipw.Dropdown(
                            description=f"{description}:",
                            options=var_meta.get("options", ()),
                            value=var_meta.get("default", None),
                            layout=LAYOUT,
                            style=STYLE,
                        )
                    else:
                        raise ValueError(f"Invalid widget type {widget_type}")

                    # Every time the value of the widget changes, we update the filled template.
                    # This migth be too much to sync the final filled template every time.
                    w.observe(self._on_template_variable_filled, names="value")

                    template_var = TemplateVariable(
                        w, [TemplateVariableLine(line_key, line_str, line_vars)]
                    )
                    self._template_variables[var] = template_var

        # Render by change the VBox children of placeholder.
        self.template_variables.children = [
            # widget is shared so we only need to get the first one.
            template_var.widget
            for template_var in self._template_variables.values()
        ]

        # Show the help text if there are template variables.
        if self.template_variables.children:
            self._help_text.layout.display = "block"

    def fill(self):
        """Use template and current widgets value to fill the template
        and update the filled_template.
        """
        self.unfilled_variables = []

        # Remove the metadata from the templates because for the final
        # filled template we don't pass it to setup traits.
        filled_templates = copy.deepcopy(self.templates)
        if "metadata" in filled_templates:
            del filled_templates["metadata"]

        for template_var in self._template_variables.values():
            for line in template_var.lines:
                # update the filled template.
                # if the widget is not filled, use the original template var string e.g. {{ var }}
                inp_dict = {}
                for _var in line.vars:
                    if self._template_variables[_var].widget.value == "":
                        variable_key = self._template_variables[_var].widget.description
                        self.unfilled_variables.append(variable_key.strip(":"))
                        inp_dict[_var] = "{{ " + _var + " }}"
                    else:
                        inp_dict[_var] = self._template_variables[_var].widget.value

                # re-render the template
                env = jinja2.Environment()
                filled_str = env.from_string(line.str).render(**inp_dict)

                # Update the filled template.
                filled_templates[line.key] = filled_str

        # assign back to trigger the trait change.
        self.filled_templates = filled_templates

    def _on_template_variable_filled(self, _):
        """Callback when a template variable is filled."""
        self.fill()


class _ResourceSetupBaseWidget(ipw.VBox):
    """The widget that allows to setup a computer and code.
    This is the building block of the `ComputationalResourcesDatabaseWidget` which
    will be directly used by the user.
    """

    success = tl.Bool(False)
    message = tl.Unicode()

    ssh_auth = None  # store the ssh auth type. Can be "password" or "2FA"

    def __init__(
        self,
        default_calc_job_plugin=None,
        enable_quick_setup=True,
        enable_detailed_setup=True,
    ):
        if not any((enable_detailed_setup, enable_quick_setup)):
            raise ValueError(
                "At least one of `enable_quick_setup` and `enable_detailed_setup` should be True."
            )

        self.enable_quick_setup = enable_quick_setup
        self.enable_detailed_setup = enable_detailed_setup

        self.quick_setup_button = ipw.Button(
            description="Quick setup",
            tooltip="Setup a computer and code in one click.",
            icon="rocket",
            button_style="success",
        )
        self.quick_setup_button.on_click(self._on_quick_setup)

        reset_button = ipw.Button(
            description="Reset",
            tooltip="Reset the resource.",
            icon="refresh",
            button_style="primary",
        )
        reset_button.on_click(self._on_reset)

        # Resource database for setup computer/code.

        self.comp_resources_database = ComputationalResourcesDatabaseWidget(
            default_calc_job_plugin=default_calc_job_plugin,
            show_reset_button=False,
        )

        # All templates
        self.template_computer_setup = TemplateVariablesWidget()
        self.template_computer_configure = TemplateVariablesWidget()
        self.template_code = TemplateVariablesWidget()

        # SSH
        self.ssh_computer_setup = SshComputerSetup()
        tl.dlink(
            (self.ssh_computer_setup, "message"),
            (self, "message"),
        )

        # Computer setup.
        self.aiida_computer_setup = AiidaComputerSetup()
        tl.dlink(
            (self.aiida_computer_setup, "message"),
            (self, "message"),
        )

        # Code setup.
        self.aiida_code_setup = AiidaCodeSetup()
        tl.dlink(
            (self.aiida_code_setup, "message"),
            (self, "message"),
        )

        # Data flow.

        # Computer template -> SSH connection setup.
        tl.dlink(
            (self.comp_resources_database, "computer_configure"),
            (self.template_computer_configure, "templates"),
        )
        tl.dlink(
            (self.template_computer_configure, "filled_templates"),
            (self.ssh_computer_setup, "ssh_config"),
        )

        # Computer template -> Computer setup.
        tl.dlink(
            (self.comp_resources_database, "computer_setup"),
            (self.template_computer_setup, "templates"),
        )
        tl.dlink(
            (self.template_computer_setup, "filled_templates"),
            (self.aiida_computer_setup, "computer_setup"),
        )

        # Computer template -> Computer configure.
        tl.dlink(
            (self.template_computer_configure, "filled_templates"),
            (self.aiida_computer_setup, "computer_configure"),
        )
        self.template_computer_configure.observe(
            self._on_template_computer_configure_metadata_change, "metadata"
        )
        self.aiida_computer_setup.on_setup_computer_success(
            self._on_setup_computer_success
        )

        # Code template -> Code setup.
        tl.dlink(
            (self.comp_resources_database, "code_setup"),
            (self.template_code, "templates"),
        )
        tl.dlink(
            (self.template_code, "filled_templates"),
            (self.aiida_code_setup, "code_setup"),
        )
        self.aiida_code_setup.on_setup_code_success(self._on_setup_code_success)

        # The widget for the detailed setup.
        description_toggle_detail_setup = ipw.HTML(
            """<div><b>Tick checkbox to setup resource step by step.</b></div>"""
        )
        self.toggle_detail_setup = ipw.Checkbox(
            description="",
            value=False,
            indent=False,
            # this narrow the checkbox to the minimum width.
            layout=ipw.Layout(width="30px"),
        )
        self.toggle_detail_setup.observe(self._on_toggle_detail_setup, names="value")
        self.detailed_setup_switch_widgets = ipw.HBox(
            children=[
                self.toggle_detail_setup,
                description_toggle_detail_setup,
            ],
            layout=ipw.Layout(justify_content="flex-end"),
        )

        detailed_setup_description_text = """<div>
            <b>Go through the steps to setup SSH connection to remote machine, computer, and code into database. </br>
            The SSH connection step can be skipped and setup afterwards.</br>
            </b>
        </div>"""
        description = ipw.HTML(detailed_setup_description_text)

        detailed_setup = ipw.Tab(
            children=[
                self.ssh_computer_setup,
                self.aiida_computer_setup,
                self.aiida_code_setup,
            ],
        )
        detailed_setup.set_title(0, "SSH connection")
        detailed_setup.set_title(1, "Computer")
        detailed_setup.set_title(2, "Code")

        self.detailed_setup_widget = ipw.VBox(
            children=[
                description,
                detailed_setup,
            ]
        )

        super().__init__(
            children=[
                ipw.HTML(
                    """<div>Please select the computer/code from a database to pre-fill the fields below.</div>
                    """
                ),
                self.comp_resources_database,
                self.template_computer_setup,
                self.template_code,
                self.template_computer_configure,
                self.ssh_computer_setup.password_box,
                self.detailed_setup_switch_widgets,
                ipw.HBox(
                    children=[
                        self.quick_setup_button,
                        reset_button,
                    ],
                    layout=ipw.Layout(justify_content="flex-end"),
                ),
                self.detailed_setup_widget,
            ],
        )

        # update the layout
        self._update_layout()

    def _update_layout(self):
        """Update the layout to hide or show the bundled quick_setup/detailed_setup."""
        # check if the password is asked for ssh connection.
        if self.ssh_auth != "password":
            self.ssh_computer_setup.password_box.layout.display = "none"
        else:
            self.ssh_computer_setup.password_box.layout.display = "block"

        # If both quick and detailed setup are enabled
        # - show the switch widget
        # - show the quick setup widget (database + template variables + poppud password box + quick setup button)
        # - hide the detailed setup widget as default
        if self.enable_detailed_setup and self.enable_quick_setup:
            self.detailed_setup_widget.layout.display = "none"
            return

        # If only quick setup is enabled
        # - hide the switch widget
        # - hide the detailed setup widget
        if self.enable_quick_setup:
            self.detailed_setup_switch_widgets.layout.display = "none"
            self.detailed_setup_widget.layout.display = "none"
            return

        # If only detailed setup is enabled
        # - hide the switch widget
        # - hide the quick setup widget
        # - hide the database widget
        # which means only the detailed setup widget is shown.
        if self.enable_detailed_setup:
            self.children = [
                self.detailed_setup_widget,
            ]

    def _on_toggle_detail_setup(self, change):
        """When the checkbox is toggled, show/hide the detailed setup."""
        if change["new"]:
            self.detailed_setup_widget.layout.display = "block"
            self.quick_setup_button.disabled = True
            # fill the template variables with the default values or the filled values.
            # If the template variables are not all filled raise a warning.
        else:
            self.detailed_setup_widget.layout.display = "none"
            self.quick_setup_button.disabled = False

    def _on_template_computer_configure_metadata_change(self, change):
        """callback when the metadata of computer_configure template is changed."""
        if change["new"] is None:
            return

        # decide whether to show the ssh password box widget.
        # Since for 2FA ssh credential, the password are not needed but set from
        # independent mechanism.
        self.ssh_auth = change["new"].get("ssh_auth", None)
        if self.ssh_auth is None:
            self.ssh_auth = "password"

        self._update_layout()

    def _on_reset(self, _=None):
        """Reset the database and the widget."""
        with self.hold_trait_notifications():
            self.reset()
            self.comp_resources_database.reset()

    def _on_quick_setup(self, _=None):
        """Go through all the setup steps automatically."""
        # Raise error if the computer is not selected.
        if not self.aiida_computer_setup.some_values_provided:
            self.message = wrap_message(
                "Please select a computer from the database.",
                MessageLevel.ERROR,
            )
            return

        # Check if all the template variables are filled.
        # If not raise a warning and return (skip the setup).
        if (
            unfilled_variables := self.template_computer_setup.unfilled_variables
            + self.template_computer_configure.unfilled_variables
            + self.template_code.unfilled_variables
        ):
            var_warn_message = ", ".join([f"<b>{v}</b>" for v in unfilled_variables])
            self.message = wrap_message(
                f"Please fill the template variables: {var_warn_message}",
                MessageLevel.WARNING,
            )
            return

        # Setup the computer and code.
        if self.aiida_computer_setup.on_setup_computer():
            self.aiida_code_setup.on_setup_code()

        # Prepare the ssh key pair and copy to remote computer.
        # This only happend when the ssh_auth is password.
        if self.ssh_auth == "password":
            try:
                self.ssh_computer_setup.key_pair_prepare()
            except ValueError as exc:
                self.message = wrap_message(
                    f"Key pair generation failed: {exc}",
                    level=MessageLevel.ERROR,
                )

            self.ssh_computer_setup.thread_ssh_copy_id()

        # For not password ssh auth, key pair is not needed.
        # There are other mechanism to set up the ssh connection.
        # But we still need to write the ssh config to the ssh config file for such as
        # proxy jump.
        if not self.ssh_computer_setup._is_in_config():
            self.ssh_computer_setup._write_ssh_config()

    def _on_setup_computer_success(self):
        """Callback that is called when the computer is successfully set up."""
        # update the computer dropdown list of code setup
        self.aiida_code_setup.refresh()

        # select the computer in the dropdown list for code setup
        label = self.aiida_computer_setup.label.value
        self.aiida_code_setup.computer.select_by_label(label)

    def _on_setup_code_success(self):
        """Callback that is called when the code is successfully set up."""
        self.success = True

    def reset(self):
        """Reset the widget."""
        # reset the database
        self.comp_resources_database.reset()

        # reset template variables
        self.template_computer_setup.reset()
        self.template_computer_configure.reset()
        self.template_code.reset()

        # reset sub widgets
        self.aiida_code_setup._reset()
        self.aiida_computer_setup._reset()

        self.ssh_computer_setup._reset()

        # essential, since if not, the same computer_configure won't trigger the `_observe_ssh_config` callback.
        self.ssh_computer_setup.ssh_config = {}

        # reset traits
        self.computer_setup = {}
        self.computer_configure = {}
        self.code_setup = {}

        self.message = ""
        self.success = False
        self.ssh_auth = None

        # The layout also reset
        self._update_layout()

        # untick the detailed switch checkbox
        self.toggle_detail_setup.value = False
