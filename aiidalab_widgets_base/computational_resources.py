import os
import subprocess
from copy import copy
from pathlib import Path

import ipywidgets as ipw
import pexpect
import shortuuid
import traitlets
from aiida import common, orm, plugins, schedulers, transports
from IPython.display import clear_output, display

from .databases import ComputationalResourcesDatabase
from .utils import yield_for_change

STYLE = {"description_width": "200px"}
LAYOUT = {"width": "350px"}


class ComputationalResourcesWidget(ipw.VBox):
    """Code selection widget.
    Attributes:

    selected_code(Unicode or Code): Trait that points to the selected Code instance.
    It can be set either to an AiiDA Code instance or to a code label (will automatically
    be replaced by the corresponding Code instance). It is linked to the 'value' trait of
    the `self.dropdown` widget.

    codes(Dict): Trait that contains a dictionary (label => Code instance) for all
    codes found in the AiiDA database for the selected plugin. It is linked
    to the 'options' trait of the `self.dropdown` widget.

    allow_hidden_codes(Bool): Trait that defines whether to show hidden codes or not.

    allow_disabled_computers(Bool): Trait that defines whether to show codes on disabled
    computers.
    """

    selected_code = traitlets.Union(
        [traitlets.Unicode(), traitlets.Instance(orm.Code)], allow_none=True
    )
    codes = traitlets.Dict(allow_none=True)
    allow_hidden_codes = traitlets.Bool(False)
    allow_disabled_computers = traitlets.Bool(False)
    input_plugin = traitlets.Unicode(allow_none=True)

    def __init__(self, description="Select code:", path_to_root="../", **kwargs):
        """Dropdown for Codes for one input plugin.

        description (str): Description to display before the dropdown.
        """
        self.output = ipw.HTML()

        self.dropdown = ipw.Dropdown(description=description, disabled=True, value=None)
        traitlets.link((self, "codes"), (self.dropdown, "options"))
        traitlets.link((self.dropdown, "value"), (self, "selected_code"))

        self.observe(
            self.refresh, names=["allow_disabled_computers", "allow_hidden_codes"]
        )

        btn_setup_new_code = ipw.Button(description="Setup new code")
        btn_setup_new_code.on_click(self.setup_new_code)
        self.button_clicked = True  # Boolean to switch on and off the computational resources setup window.

        self._setup_new_code_output = ipw.Output()

        children = [
            ipw.HBox([self.dropdown, btn_setup_new_code]),
            self._setup_new_code_output,
            self.output,
        ]
        super().__init__(children=children, **kwargs)

        # Setting up codes and computers.
        self.comp_resources_database = ComputationalResourcesDatabase(
            input_plugin=self.input_plugin
        )

        ssh_computer_setup = SshComputerSetup()
        ipw.dlink(
            (self.comp_resources_database, "ssh_config"),
            (ssh_computer_setup, "ssh_config"),
        )

        self.output_accordion = ipw.Accordion(
            children=[
                ssh_computer_setup,
                AiidaComputerSetup(),
                AiiDACodeSetup(),
            ]
        )
        self.output_accordion.set_title(0, "Set-up passwordless SSH connection")
        self.output_accordion.set_title(1, "Set-up a computer in AiiDA")
        self.output_accordion.set_title(2, "Set-up a code in AiiDA")

        self.refresh()

    def _get_codes(self):
        """Query the list of available codes."""

        user = orm.User.objects.get_default()

        return {
            self._full_code_label(c[0]): c[0]
            for c in orm.QueryBuilder()
            .append(orm.Code, filters={"attributes.input_plugin": self.input_plugin})
            .all()
            if c[0].computer.is_user_configured(user)
            and (self.allow_hidden_codes or not c[0].hidden)
            and (self.allow_disabled_computers or c[0].computer.is_user_enabled(user))
        }

    @staticmethod
    def _full_code_label(code):
        return f"{code.label}@{code.computer.label}"

    def refresh(self, _=None):
        """Refresh available codes.

        The job of this function is to look in AiiDA database, find available codes and
        put them in the dropdown attribute."""
        self.output.value = ""

        with self.hold_trait_notifications():
            self.dropdown.options = self._get_codes()
        if not self.dropdown.options:
            self.output.value = (
                f"No codes found for input plugin '{self.input_plugin}'."
            )
            self.dropdown.disabled = True
        else:
            self.dropdown.disabled = False
        self.dropdown.value = None

    @traitlets.validate("selected_code")
    def _validate_selected_code(self, change):
        """If code is provided, set it as it is. If code's label is provided,
        select the code and set it."""
        code = change["value"]
        self.output.value = ""

        # If code None, set value to None
        if code is None:
            return None

        # Check code by label.
        if isinstance(code, str):
            if code in self.codes:
                return self.codes[code]
            self.output.value = f"""No code named '<span style="color:red">{code}</span>'
            found in the AiiDA database."""

        # Check code by value.
        if isinstance(code, orm.Code):
            label = self._full_code_label(code)
            if label in self.codes:
                return code
            self.output.value = f"""The code instance '<span style="color:red">{code}</span>'
            supplied was not found in the AiiDA database."""

        # This place will never be reached, because the trait's type is checked.
        return None

    def setup_new_code(self, _=None):
        with self._setup_new_code_output:
            clear_output()
            if self.button_clicked:
                display(
                    ipw.HTML("Please select the computer/code from a database."),
                    self.comp_resources_database,
                    self.output_accordion,
                )

        self.button_clicked = not self.button_clicked


class SshComputerSetup(ipw.VBox):
    """Setup password-free access to a computer."""

    ssh_config = traitlets.Dict()

    def __init__(self, **kwargs):
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

        self._inp_private_key = ipw.FileUpload(
            accept="",
            layout=LAYOUT,
            style=STYLE,
            description="Private key",
            multiple=False,
            disabled=True,
        )
        self._verification_mode = ipw.Dropdown(
            options=["password", "private_key"],
            layout=LAYOUT,
            style=STYLE,
            value="password",
            description="Verification mode:",
            disabled=False,
        )
        self._verification_mode.observe(
            self.on_use_verification_mode_change, names="value"
        )

        self._continue_button = ipw.ToggleButton(
            description="Continue", style={"description_width": "initial"}, value=False
        )

        # Setup ssh button and output.
        btn_setup_ssh = ipw.Button(description="Setup ssh")
        btn_setup_ssh.on_click(self.on_setup_ssh)
        self._setup_ssh_out = ipw.Output()

        children = [
            self.hostname,
            self.port,
            self.username,
            self.proxy_jump,
            self._verification_mode,
            self._inp_private_key,
            btn_setup_ssh,
            self._setup_ssh_out,
        ]
        super().__init__(children, **kwargs)

    @staticmethod
    def _ssh_keygen():
        """Generate ssh key pair."""
        fpath = Path("~/.ssh/id_rsa").expanduser()
        if not fpath.exists():
            # returns non-0 if the key pair already exists
            subprocess.call(
                [
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
                ],
                stdout=subprocess.DEVNULL,
            )

    def can_login(self):
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

    def is_in_config(self):
        """Check if the config file contains host information."""
        fpath = Path("~/.ssh/config").expanduser()
        if not fpath.exists():
            return False
        cfglines = open(fpath).read().split("\n")
        return "Host " + self.hostname.value in cfglines

    def _write_ssh_config(self, private_key_abs_fname=None):
        """Put host information into the config file."""
        fpath = Path("~/.ssh/config").expanduser()
        print(f"Adding section to {fpath}")
        with open(fpath, "a") as file:
            file.write(f"Host {self.hostname.value}\n")
            file.write(f"  User {self.username.value}\n")
            file.write(f"  Port {self.port.value}\n")
            if self.proxy_jump.value != "":
                file.write(f"  ProxyJump {self.proxy_jump.value}\n")
            if private_key_abs_fname:
                file.write(f"  IdentityFile {private_key_abs_fname}\n")
            file.write("  ServerAliveInterval 5\n")

    @staticmethod
    def _add_private_key(private_key_fname, private_key_content):
        """
        param private_key_fname: string
        param private_key_content: bytes
        """
        fpath = Path(f"~/.ssh/{private_key_fname}").expanduser()
        if fpath.exists():
            # if file already exist and have the same content
            with open(fpath, "rb") as file:
                content = file.read()
                if content == private_key_content:
                    return fpath.name()

            fpath = fpath / "_" / shortuuid.uuid()
        with open(fpath, "wb") as file:
            file.write(private_key_content)

        os.chmod(fpath, 0o600)

        return fpath

    def on_setup_ssh(self, change):
        """Setup ssh, password and private key are supported"""
        with self._setup_ssh_out:
            mode = self._verification_mode.value
            self._on_setup_ssh(mode, change)

    def _on_setup_ssh(self, mode, change):
        """ATTENTION: modifying the order of operations in this function can lead to unexpected problems"""
        clear_output()

        # Always start by generating a key pair if they are not present.
        self._ssh_keygen()

        # If hostname is not provided - do not do anything.
        if self.hostname.value == "":  # check hostname
            print("Please specify the computer hostname")
            return

        if not self.is_in_config():
            self._write_ssh_config()

        # If couldn't login in the previous step, chek whether all required information is provided.
        if self.username.value == "":  # check username
            print("Please enter your ssh username")
            return

        if mode == "private_key":
            # unwrap private key file and setting temporary private_key content
            private_key_fname, private_key_content = self.__private_key
            if private_key_fname is None:  # check private key file
                print("Please upload your private key file")
                return

            # write private key in ~/.ssh/ and use the name of upload file,
            # if exist, generate random string and append to filename then override current name.
            private_key_abs_fname = self._add_private_key(
                private_key_fname, private_key_content
            )

        elif mode == "password":
            # sending public key to the main host
            @yield_for_change(self._continue_button, "value")
            def f():
                timeout = 10
                print(f"Sending public key to {self.hostname.value}... ", end="")
                str_ssh = f"ssh-copy-id {self.hostname.value}"
                child = pexpect.spawn(str_ssh)

                expectations = [
                    "assword:",  # 0
                    "Now try logging into",  # 1
                    "All keys were skipped because they already exist on the remote system",  # 2
                    "Are you sure you want to continue connecting (yes/no)?",  # 3
                    "ERROR: No identities found",  # 4
                    "Could not resolve hostname",  # 5
                    "Connection refused",  # 6
                    pexpect.EOF,
                ]

                while True:
                    try:
                        index = child.expect(
                            expectations,
                            timeout=timeout,
                        )  # final

                    except pexpect.TIMEOUT:
                        print(f"Exceeded {timeout} s timeout")
                        return False

                    if index == 0:
                        pwd = ipw.Password()
                        display(
                            ipw.HBox(
                                [
                                    ipw.HTML(
                                        child.before.splitlines()[-1] + child.after
                                    ),
                                    pwd,
                                    self._continue_button,
                                ]
                            )
                        )
                        yield
                        child.sendline(pwd.value)

                    elif index == 1:
                        print("Success.")
                        break

                    elif index == 2:
                        print("Keys are already present on the remote machine.")
                        break

                    elif index == 3:  # Adding a new host.
                        child.sendline("yes")

                    elif index == 4:
                        print(
                            "Failed\nLooks like the key pair is not present in ~/.ssh folder"
                        )
                        break

                    elif index == 5:
                        print("Failed\nUnknown hostname")
                        break

                    elif index == 6:
                        print("Failed\nConnection refused.")
                        break

                    else:
                        print("Failed\nUnknown problem")
                        print(child.before, child.after)
                        break
                child.close()
                yield

            f()

    def on_use_verification_mode_change(
        self, change
    ):  # pylint: disable=unused-argument
        """which verification mode is chosen."""
        if self._verification_mode.value == "password":
            self._inp_password.disabled = False
            self._inp_private_key.disabled = True
        if self._verification_mode.value == "private_key":
            self._inp_password.disabled = True
            self._inp_private_key.disabled = False

    @property
    def __private_key(self):
        """unwrap private key file and setting filename and file content"""
        if self._inp_private_key.value:
            (fname, _value), *_ = self._inp_private_key.value.items()
            content = copy(_value["content"])
            self._inp_private_key.value.clear()
            self._inp_private_key._counter = 0  # pylint: disable=protected-access
            return fname, content
        return None, None

    @traitlets.observe("ssh_config")
    def _observe_proxy_hostname(self, _=None):
        """Pre-filling the input fields."""
        if "hostname" in self.ssh_config:
            self.hostname.value = self.ssh_config["hostname"]
        if "port" in self.ssh_config:
            self.port.value = int(self.ssh_config["port"])
        if "proxy_jump" in self.ssh_config:
            self.proxy_jump.value = int(self.ssh_config["proxy_jump"])


class AiidaComputerSetup(ipw.VBox):
    """Inform AiiDA about a computer."""

    computer_setup = traitlets.Dict(allow_none=True)

    def __init__(self, **kwargs):

        # List of widgets to be displayed.
        inp_computer_name = ipw.Text(
            value="",
            placeholder="Will only be used within AiiDA",
            description="AiiDA computer name:",
            layout=ipw.Layout(width="500px"),
            style=STYLE,
        )

        # Hostname.
        inp_computer_hostname = ipw.Text(
            description="Hostname:", layout=ipw.Layout(width="500px"), style=STYLE
        )

        # Computer description.
        inp_computer_description = ipw.Text(
            value="",
            placeholder="No description (yet)",
            description="Computer description:",
            layout=ipw.Layout(width="500px"),
            style=STYLE,
        )

        # Directory where to run the simulations.
        inp_computer_workdir = ipw.Text(
            value="/scratch/{username}/aiida_run",
            description="Workdir:",
            layout=ipw.Layout(width="500px"),
            style=STYLE,
        )

        # Mpirun command.
        inp_mpirun_cmd = ipw.Text(
            value="mpirun -n {tot_num_mpiprocs}",
            description="Mpirun command:",
            layout=ipw.Layout(width="500px"),
            style=STYLE,
        )

        # Number of CPUs per node.
        inp_computer_ncpus = ipw.IntText(
            value=12,
            step=1,
            description="Number of CPU(s) per node:",
            layout=ipw.Layout(width="270px"),
            style=STYLE,
        )

        # Transport type.
        inp_transport_type = ipw.Dropdown(
            value="ssh",
            options=transports.Transport.get_valid_transports(),
            description="Transport type:",
            style=STYLE,
        )

        # Safe interval.
        inp_safe_interval = ipw.FloatText(
            value=30.0,
            description="Min. connection interval (sec):",
            layout=ipw.Layout(width="270px"),
            style=STYLE,
        )

        # Scheduler.
        inp_scheduler = ipw.Dropdown(
            value="slurm",
            options=schedulers.Scheduler.get_valid_schedulers(),
            description="Scheduler:",
            style=STYLE,
        )

        # Use login shell.
        self._use_login_shell = ipw.Checkbox(value=True, description="Use login shell")

        # Prepend text.
        inp_prepend_text = ipw.Textarea(
            placeholder="Text to prepend to each command execution",
            description="Prepend text:",
            layout=ipw.Layout(width="400px"),
        )

        # Append text.
        inp_append_text = ipw.Textarea(
            placeholder="Text to append to each command execution",
            description="Append text:",
            layout=ipw.Layout(width="400px"),
        )

        # Buttons and outputs.
        btn_setup_comp = ipw.Button(description="Setup computer")
        btn_setup_comp.on_click(self._on_setup_computer)
        btn_test = ipw.Button(description="Test computer")
        btn_test.on_click(self.test)
        self._setup_comp_out = ipw.Output(layout=ipw.Layout(width="500px"))
        self._test_out = ipw.Output(layout=ipw.Layout(width="500px"))

        # Organize the widgets
        children = [
            inp_computer_name,
            inp_computer_hostname,
            inp_computer_description,
            inp_computer_workdir,
            inp_mpirun_cmd,
            inp_computer_ncpus,
            inp_transport_type,
            inp_safe_interval,
            inp_scheduler,
            self._use_login_shell,
            inp_prepend_text,
            inp_append_text,
            ipw.HBox([btn_setup_comp, btn_test]),
            ipw.HBox([self._setup_comp_out, self._test_out]),
        ]

        super().__init__(children, **kwargs)

    def _configure_computer(self):
        """Create AuthInfo."""
        print("Configuring '{}'".format(self.label))
        sshcfg = transports.plugins.ssh.parse_sshconfig(self.hostname.value)
        authparams = {
            "compress": True,
            "key_filename": os.path.expanduser(
                sshcfg.get("identityfile", ["~/.ssh/id_rsa"])[0]
            ),
            "gss_auth": False,
            "gss_deleg_creds": False,
            "gss_host": self.hostname.value,
            "gss_kex": False,
            "key_policy": "WarningPolicy",
            "load_system_host_keys": True,
            "port": sshcfg.get("port", 22),
            "timeout": 60,
            "use_login_shell": self._use_login_shell.value,
            "safe_interval": self.safe_interval,
        }
        if "user" in sshcfg:
            authparams["username"] = sshcfg["user"]
        else:
            print(
                f"SSH username is not provided, please run `verdi computer configure {self.label}` "
                "from the command line."
            )
            return
        if "proxycommand" in sshcfg:
            authparams["proxy_command"] = sshcfg["proxycommand"]
        aiidauser = orm.User.objects.get_default()

        authinfo = orm.AuthInfo(
            computer=orm.Computer.objects.get(label=self.label), user=aiidauser
        )
        authinfo.set_auth_params(authparams)
        authinfo.store()
        print(
            subprocess.check_output(["verdi", "computer", "show", self.label]).decode(
                "utf-8"
            )
        )

    def _on_setup_computer(self, _=None):
        """When setup computer button is pressed."""
        with self._setup_comp_out:
            clear_output()
            if self.label is None:  # check hostname
                print("Please specify the computer name (for AiiDA)")
                return
            try:
                computer = orm.Computer.objects.get(label=self.label)
                print(f"A computer called {self.label} already exists.")
                return
            except common.NotExistent:
                pass

            print(f"Creating new computer with name '{self.label}'")
            computer = orm.Computer(
                label=self.label,
                hostname=self.hostname.value,
                description=self.description,
            )
            computer.set_transport_type(self.transport)
            computer.set_scheduler_type(self.scheduler)
            computer.set_workdir(self.work_dir)
            computer.set_mpirun_command(self.mpirun_command.split())
            computer.set_default_mpiprocs_per_machine(self.mpiprocs_per_machine)
            if self.prepend_text:
                computer.set_prepend_text(self.prepend_text)
            if self.append_text:
                computer.set_append_text(self.append_text)

            computer.store()
            self._configure_computer()

    def test(self, _=None):
        with self._test_out:
            clear_output()
            print(
                subprocess.check_output(
                    ["verdi", "computer", "test", "--print-traceback", self.label]
                ).decode("utf-8")
            )

    @traitlets.validate("mpiprocs_per_machine")
    def _validate_mpiprocs_per_machine(self, provided):  # pylint: disable=no-self-use
        return int(provided["value"])

    @traitlets.validate("safe_interval")
    def _validate_safe_interval(self, provided):  # pylint: disable=no-self-use
        return float(provided["value"])


class ComputerDropdown(ipw.VBox):
    """Widget to select a configured computer.

    Attributes:
        selected_computer(Unicode or Computer): Trait that points to the selected Computer instance.
            It can be set either to an AiiDA Computer instance or to a computer label (will
            automatically be replaced by the corresponding Computer instance). It is linked to the
            'value' trait of `self._dropdown` widget.

        computers(Dict): Trait that contains a dictionary (label => Computer instance) for all
        computers found in the AiiDA database. It is linked to the 'options' trait of
        `self._dropdown` widget.

        allow_select_disabled(Bool):  Trait that defines whether to show disabled computers.
    """

    selected_computer = traitlets.Union(
        [traitlets.Unicode(), traitlets.Instance(orm.Computer)], allow_none=True
    )
    computers = traitlets.Dict(allow_none=True)
    allow_select_disabled = traitlets.Bool(False)

    def __init__(self, description="Select computer:", path_to_root="../", **kwargs):
        """Dropdown for configured AiiDA Computers.

        description (str): Text to display before dropdown.

        path_to_root (str): Path to the app's root folder.
        """

        self.output = ipw.HTML()
        self._dropdown = ipw.Dropdown(
            options={},
            value=None,
            description=description,
            style={"description_width": "initial"},
            disabled=True,
        )
        traitlets.link((self, "computers"), (self._dropdown, "options"))
        traitlets.link((self._dropdown, "value"), (self, "selected_computer"))

        btn_refresh = ipw.Button(description="Refresh", layout=ipw.Layout(width="70px"))
        btn_refresh.on_click(self.refresh)

        self.observe(self.refresh, names="allow_select_disabled")

        self._setup_another = ipw.HTML(
            value=f"""<a href={path_to_root}aiidalab-widgets-base/notebooks/setup_computer.ipynb target="_blank">
            Setup new computer</a>"""
        )

        children = [
            ipw.HBox([self._dropdown, btn_refresh, self._setup_another]),
            self.output,
        ]
        self.refresh()
        super().__init__(children=children, **kwargs)

    def _get_computers(self):
        """Get the list of available computers."""

        # Getting the current user.
        user = orm.User.objects.get_default()

        return {
            c[0].label: c[0]
            for c in orm.QueryBuilder().append(orm.Computer).all()
            if c[0].is_user_configured(user)
            and (self.allow_select_disabled or c[0].is_user_enabled(user))
        }

    def refresh(self, _=None):
        """Refresh the list of configured computers."""
        self.output.value = ""
        with self.hold_trait_notifications():  # pylint: disable=not-context-manager
            self._dropdown.options = self._get_computers()
        if not self.computers:
            self.output.value = "No computers found."
            self._dropdown.disabled = True
        else:
            self._dropdown.disabled = False

        self._dropdown.value = None

    @traitlets.validate("selected_computer")
    def _validate_selected_computer(self, change):
        """Select computer either by label or by class instance."""
        computer = change["value"]
        self.output.value = ""
        if not computer:
            return None
        if isinstance(computer, str):
            if computer in self.computers:
                return self.computers[computer]
            self.output.value = f"""Computer instance '<span style="color:red">{computer}</span>'
            is not configured in your AiiDA profile."""
            return None

        if isinstance(computer, orm.Computer):
            if computer.label in self.computers:
                return computer
            self.output.value = f"""Computer instance '<span style="color:red">{computer.label}</span>'
            is not configured in your AiiDA profile."""
        return None


class AiiDACodeSetup(ipw.VBox):
    """Class that allows to setup AiiDA code"""

    code_setup = traitlets.Dict(allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):

        style = {"description_width": "200px"}

        # Code label.
        inp_label = ipw.Text(
            description="AiiDA code label:",
            layout=ipw.Layout(width="500px"),
            style=style,
        )

        # Computer on which the code is installed. Two dlinks are needed to make sure we get a Computer instance.
        self.inp_computer = ComputerDropdown(
            path_to_root=path_to_root, layout={"margin": "0px 0px 0px 125px"}
        )

        # Code plugin.
        self.inp_code_plugin = ipw.Dropdown(
            options=sorted(
                plugins.entry_point.get_entry_point_names("aiida.calculations")
            ),
            description="Code plugin:",
            layout=ipw.Layout(width="500px"),
            style=style,
        )

        # Code description.
        inp_description = ipw.Text(
            placeholder="No description (yet)",
            description="Code description:",
            layout=ipw.Layout(width="500px"),
            style=style,
        )

        inp_abs_path = ipw.Text(
            placeholder="/path/to/executable",
            description="Absolute path to executable:",
            layout=ipw.Layout(width="500px"),
            style=style,
        )

        inp_prepend_text = ipw.Textarea(
            placeholder="Text to prepend to each command execution",
            description="Prepend text:",
            layout=ipw.Layout(width="400px"),
        )

        inp_append_text = ipw.Textarea(
            placeholder="Text to append to each command execution",
            description="Append text:",
            layout=ipw.Layout(width="400px"),
        )

        btn_setup_code = ipw.Button(description="Setup code")
        btn_setup_code.on_click(self._setup_code)
        self._setup_code_out = ipw.Output()
        children = [
            inp_label,
            self.inp_computer,
            self.inp_code_plugin,
            inp_description,
            inp_abs_path,
            inp_prepend_text,
            inp_append_text,
            btn_setup_code,
            self._setup_code_out,
        ]
        super().__init__(children, **kwargs)

    @traitlets.validate("input_plugin")
    def _validate_input_plugin(self, proposal):
        plugin = proposal["value"]
        return plugin if plugin in self.inp_code_plugin.options else None

    def _setup_code(self, _=None):
        """Setup an AiiDA code."""
        with self._setup_code_out:
            clear_output()
            if self.label is None:
                print("You did not specify code label.")
                return
            if not self.remote_abs_path:
                print("You did not specify absolute path to the executable.")
                return
            if not self.inp_computer.selected_computer:
                print(
                    "Please specify a computer that is configured in your AiiDA profile."
                )
                return False
            if not self.input_plugin:
                print(
                    "Please specify an input plugin that is installed in your AiiDA environment."
                )
                return False
            if self.exists():
                print(
                    f"Code {self.label}@{self.inp_computer.selected_computer.label} already exists."
                )
                return
            code = orm.Code(
                remote_computer_exec=(
                    self.inp_computer.selected_computer,
                    self.remote_abs_path,
                )
            )
            code.label = self.label
            code.description = self.description
            code.set_input_plugin_name(self.input_plugin)
            code.set_prepend_text(self.prepend_text)
            code.set_append_text(self.append_text)
            code.store()
            code.reveal()
            full_string = f"{self.label}@{self.inp_computer.selected_computer.label}"
            print(
                subprocess.check_output(["verdi", "code", "show", full_string]).decode(
                    "utf-8"
                )
            )

    def exists(self):
        """Returns True if the code exists, returns False otherwise."""
        if not self.label:
            return False
        try:
            orm.Code.get_from_string(
                f"{self.label}@{self.inp_computer.selected_computer.label}"
            )
            return True
        except common.MultipleObjectsError:
            return True
        except common.NotExistent:
            return False


def CodeDropdown(*args, **kwargs):
    from warnings import warn

    warn(
        "'CodeDropdown' is deprecated, please use 'ComputationalResourcesWidget' instead."
    )
    return ComputationalResourcesWidget(*args, **kwargs)
