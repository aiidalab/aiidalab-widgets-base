import enum
import os
import subprocess
import threading
from copy import copy
from pathlib import Path
from uuid import UUID

import ipywidgets as ipw
import pexpect
import shortuuid
import traitlets
from aiida import common, orm, plugins
from aiida.common.exceptions import NotExistent
from aiida.orm.utils.builders.computer import ComputerBuilder
from aiida.transports.plugins.ssh import parse_sshconfig
from humanfriendly import InvalidSize, parse_size
from IPython.display import clear_output, display

from .databases import ComputationalResourcesDatabaseWidget
from .utils import StatusHTML

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

    value = traitlets.Unicode(allow_none=True)
    codes = traitlets.Dict(allow_none=True)
    allow_hidden_codes = traitlets.Bool(False)
    allow_disabled_computers = traitlets.Bool(False)
    default_calc_job_plugin = traitlets.Unicode(allow_none=True)

    def __init__(self, description="Select code:", path_to_root="../", **kwargs):
        """Dropdown for Codes for one input plugin.

        description (str): Description to display before the dropdown.
        """
        self.output = ipw.HTML()
        self.setup_message = StatusHTML(clear_after=30)
        self.code_select_dropdown = ipw.Dropdown(
            description=description,
            disabled=True,
            value=None,
            style={"description_width": "initial"},
        )
        traitlets.directional_link(
            (self, "codes"),
            (self.code_select_dropdown, "options"),
            transform=lambda x: [(key, x[key]) for key in x],
        )
        traitlets.directional_link(
            (self.code_select_dropdown, "options"),
            (self, "codes"),
            transform=lambda x: {c[0]: c[1] for c in x},
        )
        traitlets.link((self.code_select_dropdown, "value"), (self, "value"))

        self.observe(
            self.refresh, names=["allow_disabled_computers", "allow_hidden_codes"]
        )

        self.btn_setup_new_code = ipw.ToggleButton(description="Setup new code")
        self.btn_setup_new_code.observe(self._setup_new_code, "value")

        self._setup_new_code_output = ipw.Output(layout={"width": "500px"})

        children = [
            ipw.HBox([self.code_select_dropdown, self.btn_setup_new_code]),
            self._setup_new_code_output,
            self.output,
        ]
        super().__init__(children=children, **kwargs)

        # Setting up codes and computers.
        self.comp_resources_database = ComputationalResourcesDatabaseWidget(
            default_calc_job_plugin=self.default_calc_job_plugin
        )

        self.ssh_computer_setup = SshComputerSetup()
        ipw.dlink(
            (self.ssh_computer_setup, "message"),
            (self.setup_message, "message"),
        )

        ipw.dlink(
            (self.comp_resources_database, "ssh_config"),
            (self.ssh_computer_setup, "ssh_config"),
        )

        self.aiida_computer_setup = AiidaComputerSetup()
        ipw.dlink(
            (self.aiida_computer_setup, "message"),
            (self.setup_message, "message"),
        )
        ipw.dlink(
            (self.comp_resources_database, "computer_setup"),
            (self.aiida_computer_setup, "computer_setup"),
        )

        # Set up AiiDA code.
        self.aiida_code_setup = AiidaCodeSetup()
        ipw.dlink(
            (self.aiida_code_setup, "message"),
            (self.setup_message, "message"),
        )
        ipw.dlink(
            (self.comp_resources_database, "code_setup"),
            (self.aiida_code_setup, "code_setup"),
        )
        self.aiida_code_setup.on_setup_code_success(self.refresh)

        # After a successfull computer setup the codes widget should be refreshed.
        # E.g. the list of available computers needs to be updated.
        self.aiida_computer_setup.on_setup_computer_success(
            self.aiida_code_setup.refresh
        )

        # Quick setup.
        quick_setup_button = ipw.Button(description="Quick Setup")
        quick_setup_button.on_click(self.quick_setup)
        self.quick_setup = ipw.VBox(
            children=[
                self.ssh_computer_setup.username,
                quick_setup_button,
                self.aiida_code_setup.setup_code_out,
            ]
        )

        # Detailed setup.
        self.detailed_setup = ipw.Accordion(
            children=[
                self.ssh_computer_setup,
                self.aiida_computer_setup,
                self.aiida_code_setup,
            ]
        )
        self.detailed_setup.set_title(0, "Set up password-less SSH connection")
        self.detailed_setup.set_title(1, "Set up a computer in AiiDA")
        self.detailed_setup.set_title(2, "Set up a code in AiiDA")

        self.refresh()

    def quick_setup(self, _=None):
        """Go through all the setup steps automatically."""
        with self.hold_trait_notifications():
            self.ssh_computer_setup._on_setup_ssh_button_pressed()
            if self.aiida_computer_setup.on_setup_computer():
                self.aiida_code_setup.on_setup_code()

    def _get_codes(self):
        """Query the list of available codes."""

        user = orm.User.collection.get_default()

        return [
            (self._full_code_label(c[0]), c[0].uuid)
            for c in orm.QueryBuilder()
            .append(
                orm.Code,
                filters={"attributes.input_plugin": self.default_calc_job_plugin},
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
                self.output.value = f"No codes found for default calcjob plugin '{self.default_calc_job_plugin}'."
                self.code_select_dropdown.disabled = True
            else:
                self.code_select_dropdown.disabled = False
            self.code_select_dropdown.value = None

    @traitlets.validate("value")
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
                    "width": "500px",
                    "border": "1px solid gray",
                }
                if self.comp_resources_database.database:
                    setup_tab = ipw.Tab(
                        children=[self.quick_setup, self.detailed_setup]
                    )
                    setup_tab.set_title(0, "Quick Setup")
                    setup_tab.set_title(1, "Detailed Setup")
                    children = [
                        ipw.HTML(
                            """Please select the computer/code from a database to pre-fill the fields below."""
                        ),
                        self.comp_resources_database,
                        self.ssh_computer_setup.password_box,
                        self.setup_message,
                        setup_tab,
                    ]
                else:
                    # Display only Detailed Setup if DB is empty
                    setup_tab = ipw.Tab(children=[self.detailed_setup])
                    setup_tab.set_title(0, "Detailed Setup")
                    children = [self.setup_message, setup_tab]
                display(*children)
            else:
                self._setup_new_code_output.layout = {
                    "width": "500px",
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

    ssh_config = traitlets.Dict()
    ssh_connection_state = traitlets.UseEnum(
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
    message = traitlets.Unicode()
    password_message = traitlets.Unicode("The passwordless enabling log.")

    def __init__(self, **kwargs):
        self._ssh_connection_message = None
        self._password_message = ipw.HTML()
        ipw.dlink((self, "password_message"), (self._password_message, "value"))
        self._ssh_password = ipw.Password(layout={"width": "150px"}, disabled=True)
        self._continue_with_password_button = ipw.Button(
            description="Continue", layout={"width": "100px"}, disabled=True
        )
        self._continue_with_password_button.on_click(self._send_password)

        self.password_box = ipw.VBox(
            [
                self._password_message,
                ipw.HBox([self._ssh_password, self._continue_with_password_button]),
            ]
        )

        # Username.
        self.username = ipw.Text(
            description="SSH username:", layout=LAYOUT, style=STYLE
        )

        # Port.
        self.port = ipw.IntText(
            description="SSH port:",
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
        self.message = "Generating SSH key pair."
        fpath = Path.home() / ".ssh" / "id_rsa"
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
            subprocess.run(keygen_cmd, capture_output=True)

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
        """Check if the config file contains host information."""
        fpath = Path.home() / ".ssh" / "config"
        if not fpath.exists():
            return False
        with open(fpath) as f:
            cfglines = f.read().split("\n")
        return "Host " + self.hostname.value in cfglines

    def _write_ssh_config(self, private_key_abs_fname=None):
        """Put host information into the config file."""
        fpath = Path.home() / ".ssh"
        if not fpath.exists():
            fpath.mkdir()
            fpath.chmod(0o700)

        fpath = fpath / "config"

        self.message = f"Adding {self.hostname.value} section to {fpath}"
        with open(fpath, "a") as file:
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

    def _on_setup_ssh_button_pressed(self, _=None):
        # Always start by generating a key pair if they are not present.
        self._ssh_keygen()

        # If hostname & username are not provided - do not do anything.
        if self.hostname.value == "":  # check hostname
            self.message = "Please specify the computer hostname."
            return False

        if self.username.value == "":  # check username
            self.message = "Please specify your SSH username."
            return False

        private_key_abs_fname = None
        if self._verification_mode.value == "private_key":
            # unwrap private key file and setting temporary private_key content
            private_key_abs_fname, private_key_content = self._private_key
            if private_key_abs_fname is None:  # check private key file
                self.message = "Please upload your private key file."
                return False

            # Write private key in ~/.ssh/ and use the name of upload file,
            # if exist, generate random string and append to filename then override current name.
            self._add_private_key(private_key_abs_fname, private_key_content)

        if not self._is_in_config():
            self._write_ssh_config(private_key_abs_fname=private_key_abs_fname)

        # Copy public key on the remote computer.
        ssh_connection_thread = threading.Thread(target=self._ssh_copy_id)
        ssh_connection_thread.start()

    def _ssh_copy_id(self):
        """Run the ssh-copy-id command and follow it until it is completed."""
        timeout = 30
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
                self._ssh_password.disabled = True
                self._continue_with_password_button.disabled = True
                self.password_message = (
                    f"Exceeded {timeout} s timeout. Please start again."
                )
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
        self._ssh_password.disabled = True
        self._continue_with_password_button.disabled = True
        self._ssh_connection_process.sendline(self._ssh_password.value)

    @traitlets.observe("ssh_connection_state")
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

        self.ssh_connection_state = SshConnectionState.waiting_for_input

    def _on_verification_mode_change(self, change):
        """which verification mode is chosen."""
        with self._verification_mode_output:
            clear_output()
            if self._verification_mode.value == "private_key":
                display(self._inp_private_key)
            elif self._verification_mode.value == "public_key":
                public_key = Path.home() / ".ssh" / "id_rsa.pub"
                if public_key.exists():
                    display(
                        ipw.HTML(
                            f"""<pre style="background-color: #253239; color: #cdd3df; line-height: normal; custom=test">{public_key.read_text()}</pre>""",
                            layout={"width": "100%"},
                        )
                    )

    @property
    def _private_key(self):
        """Unwrap private key file and setting filename and file content."""
        if self._inp_private_key.value:
            (fname, _value), *_ = self._inp_private_key.value.items()
            content = copy(_value["content"])
            self._inp_private_key.value.clear()
            self._inp_private_key._counter = 0  # pylint: disable=protected-access
            return fname, content
        return None, None

    @staticmethod
    def _add_private_key(private_key_fname, private_key_content):
        """
        param private_key_fname: string
        param private_key_content: bytes
        """
        fpath = Path.home() / ".ssh" / private_key_fname
        if fpath.exists():
            # If the file already exist and has the same content, we do nothing.
            if fpath.read_bytes() == private_key_content:
                return fpath
            # If the content is different, we make a new file with a unique name.
            fpath = fpath / "_" / shortuuid.uuid()

        fpath.write_bytes(private_key_content)

        fpath.chmod(0o600)

        return fpath

    def _reset(self):
        self.hostname.value = ""
        self.port.value = 22
        self.username.value = ""
        self.proxy_jump.value = ""
        self.proxy_command.value = ""

    @traitlets.observe("ssh_config")
    def _observe_ssh_config(self, _=None):
        """Pre-filling the input fields."""
        if not self.ssh_config:
            self._reset()

        if "hostname" in self.ssh_config:
            self.hostname.value = self.ssh_config["hostname"]
        if "port" in self.ssh_config:
            self.port.value = int(self.ssh_config["port"])
        if "proxy_jump" in self.ssh_config:
            self.proxy_jump.value = self.ssh_config["proxy_jump"]
        if "proxy_command" in self.ssh_config:
            self.proxy_command.value = self.ssh_config["proxy_command"]


class AiidaComputerSetup(ipw.VBox):
    """Inform AiiDA about a computer."""

    computer_setup = traitlets.Dict(allow_none=True)
    message = traitlets.Unicode()

    def __init__(self, **kwargs):
        self._on_setup_computer_success = []

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
            value="/scratch/{username}/aiida_run",
            description="Workdir:",
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
            layout={"visibility": "hidden"},
        )
        self.default_memory_per_machine = None

        def observe_memory_per_machine(change):
            """Check if the string defining memory is valid."""
            memory_wrong_syntax.layout.visibility = "hidden"
            if not self.default_memory_per_machine_widget.value:
                self.default_memory_per_machine = None
                return
            try:
                self.default_memory_per_machine = (
                    int(parse_size(change["new"], binary=True) / 1024) or None
                )
                memory_wrong_syntax.layout.visibility = "hidden"
            except InvalidSize:
                memory_wrong_syntax.layout.visibility = "visible"
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
        self._test_out = ipw.Output(layout=LAYOUT)

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

    def _configure_computer(self, computer: orm.Computer):
        """Configure the computer"""
        sshcfg = parse_sshconfig(self.hostname.value)
        authparams = {
            "port": int(sshcfg.get("port", 22)),
            "look_for_keys": True,
            "key_filename": os.path.expanduser(
                sshcfg.get("identityfile", ["~/.ssh/id_rsa"])[0]
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
        try:
            authparams["username"] = sshcfg["user"]
        except KeyError as exc:
            message = "SSH username is not provided"
            self.message = message
            raise RuntimeError(message) from exc

        if "proxycommand" in sshcfg:
            authparams["proxy_command"] = sshcfg["proxycommand"]
        elif "proxyjump" in sshcfg:
            authparams["proxy_jump"] = sshcfg["proxyjump"]

        # user default AiiDA user
        user = orm.User.collection.get_default()
        computer.configure(user=user, **authparams)

        return True

    def _run_callbacks_if_computer_exists(self, label):
        """Run things on an existing computer"""
        try:
            orm.Computer.objects.get(label=label)
            for function in self._on_setup_computer_success:
                function()
        except common.NotExistent:
            return False
        else:
            return True

    def on_setup_computer(self, _=None):
        """Create a new computer."""
        if self.label.value == "":  # check hostname
            self.message = "Please specify the computer name (for AiiDA)"
            return False

        # If the computer already exists, we just run the registered functions and return
        if self._run_callbacks_if_computer_exists(self.label.value):
            self.message = f"A computer called {self.label.value} already exists."
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
            self._configure_computer(computer)
        except (
            ComputerBuilder.ComputerValidationError,
            common.exceptions.ValidationError,
            RuntimeError,
        ) as err:
            self.message = f"Failed to setup computer {type(err).__name__}: {err}"
            return False
        else:
            computer.store()

        # Callbacks will not run if the computer is not stored
        if self._run_callbacks_if_computer_exists(self.label.value):
            self.message = f"Computer<{computer.pk}> {computer.label} created"
            return True

        self.message = f"Failed to create computer {computer.label}"
        return False

    def on_setup_computer_success(self, function):
        self._on_setup_computer_success.append(function)

    def test(self, _=None):
        with self._test_out:
            clear_output()
            print(
                subprocess.check_output(
                    ["verdi", "computer", "test", "--print-traceback", self.label.value]
                ).decode("utf-8")
            )

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

    @traitlets.observe("computer_setup")
    def _observe_computer_setup(self, _=None):
        # Setup.
        if not self.computer_setup:
            self._reset()
            return
        if "setup" in self.computer_setup:
            for key, value in self.computer_setup["setup"].items():
                if key == "default_memory_per_machine":
                    self.default_memory_per_machine_widget.value = f"{value} KB"
                elif hasattr(self, key):
                    getattr(self, key).value = value

        # Configure.
        if "configure" in self.computer_setup:
            for key, value in self.computer_setup["configure"].items():
                if hasattr(self, key):
                    getattr(self, key).value = value


class AiidaCodeSetup(ipw.VBox):
    """Class that allows to setup AiiDA code"""

    code_setup = traitlets.Dict(allow_none=True)
    message = traitlets.Unicode()

    def __init__(self, path_to_root="../", **kwargs):
        self._on_setup_code_success = []

        # Code label.
        self.label = ipw.Text(
            description="AiiDA code label:",
            layout=LAYOUT,
            style=STYLE,
        )

        # Computer on which the code is installed. The value of this widget is
        # the UUID of the selected computer.
        self.computer = ComputerDropdownWidget(
            path_to_root=path_to_root,
        )

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

    @traitlets.validate("default_calc_job_plugin")
    def _validate_default_calc_job_plugin(self, proposal):
        plugin = proposal["value"]
        return plugin if plugin in self.default_calc_job_plugin.options else None

    def on_setup_code(self, _=None):
        """Setup an AiiDA code."""
        with self.setup_code_out:
            clear_output()

            if not self.computer.value:
                self.message = "Please select an existing computer."
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

            kwargs = {key: getattr(self, key).value for key in items_to_configure}

            # set computer from its widget value the UUID of the computer.
            computer = orm.load_computer(self.computer.value)

            # Checking if the code with this name already exists
            qb = orm.QueryBuilder()
            qb.append(orm.Computer, filters={"uuid": computer.uuid}, tag="computer")
            qb.append(
                orm.InstalledCode,
                with_computer="computer",
                filters={"label": kwargs["label"]},
            )
            if qb.count() > 0:
                self.message = (
                    f"Code {kwargs['label']}@{computer.label} already exists."
                )
                return False

            try:
                code = orm.InstalledCode(computer=computer, **kwargs)
            except (common.exceptions.InputValidationError, KeyError) as exception:
                self.message = f"Invalid inputs: {exception}"
                return False

            try:
                code.store()
                code.is_hidden = False
            except common.exceptions.ValidationError as exception:
                self.message = f"Unable to store the Code: {exception}"
                return False

            for function in self._on_setup_code_success:
                function()

            self.message = f"Code<{code.pk}> {code.full_label} created"

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

    @traitlets.observe("code_setup")
    def _observe_code_setup(self, _=None):
        # Setup.
        self.computer.refresh()
        if not self.code_setup:
            self._reset()
        for key, value in self.code_setup.items():
            if hasattr(self, key):
                if key == "default_calc_job_plugin":
                    try:
                        getattr(self, key).label = value
                    except traitlets.TraitError:
                        self.message = f"Input plugin {value} is not installed."
                elif key == "computer":
                    # check if the computer is set by load the label.
                    # if the computer not set put the value to None as placeholder for
                    # ComputerDropdownWidget it will refresh after the computer set up.
                    # if the computer is set pass the UUID to ComputerDropdownWdiget.
                    try:
                        computer = orm.load_computer(value)
                    except NotExistent:
                        getattr(self, key).value = None
                    else:
                        getattr(self, key).value = computer.uuid
                else:
                    getattr(self, key).value = value


class ComputerDropdownWidget(ipw.VBox):
    """Widget to select a configured computer.

    Attributes:
        value(computer UUID): Trait that points to the selected Computer instance.
            It can be set to an AiiDA Computer UUID. It is linked to the
            'value' trait of `self._dropdown` widget.
        computers(Dict): Trait that contains a dictionary (label => Computer UUID) for all
        computers found in the AiiDA database. It is linked to the 'options' trait of
        `self._dropdown` widget.
        allow_select_disabled(Bool):  Trait that defines whether to show disabled computers.
    """

    value = traitlets.Unicode(allow_none=True)
    computers = traitlets.Dict(allow_none=True)
    allow_select_disabled = traitlets.Bool(False)

    def __init__(self, description="Select computer:", path_to_root="../", **kwargs):
        """Dropdown for configured AiiDA Computers.

        description (str): Text to display before dropdown.

        path_to_root (str): Path to the app's root folder.
        """

        self.output = ipw.HTML()
        self._dropdown = ipw.Dropdown(
            value=None,
            description=description,
            style=STYLE,
            layout=LAYOUT,
            disabled=True,
        )
        traitlets.directional_link(
            (self, "computers"),
            (self._dropdown, "options"),
            transform=lambda x: [(key, x[key]) for key in x],
        )
        traitlets.directional_link(
            (self._dropdown, "options"),
            (self, "computers"),
            transform=lambda x: {c[0]: c[1] for c in x},
        )
        traitlets.link((self._dropdown, "value"), (self, "value"))

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
        user = orm.User.collection.get_default()

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

    @traitlets.validate("value")
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
