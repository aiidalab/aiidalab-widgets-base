from __future__ import print_function
from __future__ import absolute_import

import pexpect
import ipywidgets as ipw

from os import path
from copy import copy
from IPython.display import clear_output
from subprocess import check_output, call
from traitlets import Int

from aiida.orm import Computer
from aiida.orm import User
from aiida.backends.utils import get_backend_type
from aiida.common import NotExistent
from aiida.transports.plugins.ssh import parse_sshconfig


VALID_SSH_COMPUTER_SETUP_ARGUMETNS = {
    'hostname', 'username', 'proxy_hostname', 'proxy_username'
}
VALID_AIIDA_COMPUTER_SETUP_ARGUMETNS = {
    'name', 'hostname', 'description', 'workdir', 'mpirun_cmd', 'ncpus',
    'transport_type', 'scheduler', 'prepend_text', 'append_text'
}


def valid_arguments(arguments, valid_arguments):
    result = {}
    for key, value in arguments.items():
        if key in valid_arguments:
            if type(value) is tuple or type(value) is list:
                result[key] = '\n'.join(value)
            else:
                result[key] = value
    return result


def extract_sshcomputersetup_arguments(arguments):
    return valid_arguments(arguments, VALID_SSH_COMPUTER_SETUP_ARGUMETNS)


def extract_aiidacomputer_arguments(arguments):
    return valid_arguments(arguments, VALID_AIIDA_COMPUTER_SETUP_ARGUMETNS)


class SshComputerSetup(ipw.VBox):
    setup_counter = Int(0)  # Traitlet to inform other widgets about changes

    def __init__(self, **kwargs):
        style = {"description_width": "200px"}
        computer_image = ipw.HTML(
            '<img width="200px" src="./miscellaneous/images/computer.png">')
        self._inp_username = ipw.Text(description="SSH username:",
                                      layout=ipw.Layout(width="350px"),
                                      style=style)
        self._inp_password = ipw.Password(description="SSH password:",
                                          layout=ipw.Layout(width="130px"),
                                          style=style)
        # Computer ssh settings
        self._inp_computer_hostname = ipw.Text(
            description="Computer name:",
            layout=ipw.Layout(width="350px"),
            style=style)
        self._use_proxy = ipw.Checkbox(value=False, description='Use proxy')
        self._use_proxy.observe(self.on_use_proxy_change, names='value')

        # Proxy ssh settings
        self._inp_proxy_address = ipw.Text(description="Proxy server address:",
                                           layout=ipw.Layout(width="350px"),
                                           style=style)
        self._use_diff_proxy_username = ipw.Checkbox(
            value=False,
            description='Use different username and password',
            layout={'width': 'initial'})
        self._use_diff_proxy_username.observe(
            self.on_use_diff_proxy_username_change, names='value')

        self._inp_proxy_username = ipw.Text(
            value='',
            description="Proxy server username:",
            layout=ipw.Layout(width="350px"),
            style=style)
        self._inp_proxy_password = ipw.Password(
            value='',
            description="Proxy server password:",
            layout=ipw.Layout(width="138px"),
            style=style)
        self._btn_setup_ssh = ipw.Button(description="Setup ssh")
        self._btn_setup_ssh.on_click(self.on_setup_ssh)
        self._setup_ssh_out = ipw.Output()

        # Check if some settings were already provided
        self._predefine_settings(**kwargs)

        # Defining widgets positions
        computer_ssh_box = ipw.VBox([
            self._inp_computer_hostname, self._inp_username,
            self._inp_password, self._use_proxy
        ],
                                    layout=ipw.Layout(width="400px"))

        self._proxy_user_password_box = ipw.VBox(
            [self._inp_proxy_username, self._inp_proxy_password],
            layout={'visibility': 'hidden'})

        self._proxy_ssh_box = ipw.VBox([
            self._inp_proxy_address, self._use_diff_proxy_username,
            self._proxy_user_password_box
        ],
                                       layout={
                                           'visibility': 'hidden',
                                           'width': '400px'
                                       })

        children = [
            ipw.HBox([computer_image, computer_ssh_box, self._proxy_ssh_box]),
            self._btn_setup_ssh, self._setup_ssh_out
        ]

        super(SshComputerSetup, self).__init__(children, **kwargs)

    def _predefine_settings(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(
                    "'{}' object has no attirubte '{}'".format(self, key))

    def _ssh_keygen(self):
        fn = path.expanduser("~/.ssh/id_rsa")
        if not path.exists(fn):
            print("Creating ssh key pair")
            # returns non-0 if the key pair already exists
            call(["ssh-keygen", "-f", fn, "-t", "rsa", "-N", ""])

    def is_host_known(self, hostname=None):
        if hostname is None:
            hostname = self.hostname
        fn = path.expanduser("~/.ssh/known_hosts")
        if not path.exists(fn):
            return False
        return call(["ssh-keygen", "-F", hostname]) == 0

    def _make_host_known(self, hostname, proxycmd=[]):
        fn = path.expanduser("~/.ssh/known_hosts")
        print("Adding keys from %s to %s" % (hostname, fn))
        hashes = check_output(proxycmd + ["ssh-keyscan", "-H", hostname])
        with open(fn, "a") as f:
            f.write(hashes)

    def can_login(self, silent=False):
        if self.username is None:  # if I can't find the username - I must fail
            return False
        userhost = self.username + "@" + self.hostname
        if not silent:
            print("Trying ssh " + userhost + "... ", end='')
        # With BatchMode on, no password prompt or other interaction is attempted,
        # so a connect that requires a password will fail.
        ret = call([
            "ssh", userhost, "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            "true"
        ])
        if not silent:
            print("Ok" if ret == 0 else "Failed")
        return ret == 0

    def is_in_config(self):
        fn = path.expanduser("~/.ssh/config")
        if not path.exists(fn):
            return False
        cfglines = open(fn).read().split("\n")
        return "Host " + self.hostname in cfglines

    def _write_ssh_config(self, proxycmd=''):
        fn = path.expanduser("~/.ssh/config")
        print("Adding section to " + fn)
        with open(fn, "a") as f:
            f.write("Host " + self.hostname + "\n")
            f.write("User " + self.username + "\n")
            if proxycmd:
                f.write("ProxyCommand ssh -q -Y " + proxycmd +
                        " netcat %h %p\n")
            f.write("ServerAliveInterval 5\n")

    def _send_pubkey(self, hostname, username, password, proxycmd=''):
        from pexpect import TIMEOUT
        timeout = 10
        print("Sending public key to {}... ".format(hostname), end='')
        str_ssh = 'ssh-copy-id {}@{}'.format(username, hostname)
        if proxycmd:
            str_ssh += ' -o "ProxyCommand ssh -q -Y ' + proxycmd + ' netcat %h %p\n"'
        child = pexpect.spawn(str_ssh)
        try:
            index = child.expect(
                [
                    's password:',  # 0
                    'ERROR: No identities found',  # 1
                    'All keys were skipped because they already exist on the remote system',  # 2
                    'Could not resolve hostname',  # 3
                    pexpect.EOF
                ],
                timeout=timeout)  # final
        except TIMEOUT:
            print("Exceeded {} s timeout".format(timeout))
            return False

        if index == 0:
            child.sendline(password)
            try:
                child.expect("Now try logging into", timeout=5)
            except:
                print("Failed")
                print("Please check your username and/or password")
                return False
            print("Ok")
            child.close()
            return True
        elif index == 1:
            print("Failed")
            print("Looks like the key pair is not present in ~/.ssh folder")
            return False
        elif index == 2:
            print("Keys are already there")
            return True
        elif index == 3:
            print("Failed")
            print("Unknown hostname")
            return False
        else:
            print("Failed")
            print("Unknown problem")
            print(child.before, child.after)
            child.close()
            return False

    def _configure_proxy(self, password, proxy_password):
        # if proxy IS required
        if self._use_proxy.value:
            # again some standard checks if proxy server parameters are provided
            if self.proxy_hostname is None:  # hostname
                print("Please specify the proxy server hostname")
                return False, ''
            # if proxy username and password must be different from the main computer - they should be provided
            if self._use_diff_proxy_username.value:
                # check username
                if not self.proxy_username is None:
                    proxy_username = self.proxy_username
                else:
                    print("Please specify the proxy server username")
                    return False, ''
                # check password
                if len(proxy_password.strip()) == 0:
                    print("Please specify the proxy server password")
                    return False, ''
            else:  # if username and password are the same as for the main computer
                proxy_username = self.username
                proxy_password = password
            # make proxy server known
            if not self.is_host_known(self.proxy_hostname):
                self._make_host_known(self.proxy_hostname)
            # Finally trying to connect
            if self._send_pubkey(self.proxy_hostname, proxy_username,
                                 proxy_password):
                return True, proxy_username + '@' + self.proxy_hostname
            else:
                print("Could not send public key to {} (proxy server).".format(
                    self.proxy_hostname))
                return False, ''
        # if proxy is NOT required
        else:
            return True, ''

    def on_setup_ssh(self, b):
        """ATTENTION: modifying the order of operations in this function can lead to unexpected problems"""
        with self._setup_ssh_out:
            clear_output()
            self._ssh_keygen()

            #temporary passwords
            password = self.__password
            proxy_password = self.__proxy_password

            # step 1: if hostname is not provided - do not do anything
            if self.hostname is None:  # check hostname
                print("Please specify the computer hostname")
                return

            # step 2: check if password-free access was enabled earlier
            if self.can_login():
                print("Password-free access is already enabled")
                # it can still happen that password-free access is enabled
                # but host is not present in the config file - fixing this
                if not self.is_in_config():
                    self._write_ssh_config(
                    )  # we do not use proxy here, because if computer
                    # can be accessed without any info in the config - proxy is not needed.
                    self.setup_counter += 1  # only if config file has changed - increase setup_counter
                return

            # step 3: if can't login already, chek whether all required information is provided
            if self.username is None:  # check username
                print("Please enter your ssh username")
                return
            if len(password.strip()) == 0:  # check password
                print("Please enter your ssh password")
                return

            # step 4: get the right commands to access the proxy server (if provided)
            success, proxycmd = self._configure_proxy(password, proxy_password)
            if not success:
                return

            # step 5: make host known by ssh on the proxy server
            if not self.is_host_known():
                self._make_host_known(self.hostname,
                                      ['ssh'] + [proxycmd] if proxycmd else [])

            # step 6: sending public key to the main host
            if not self._send_pubkey(self.hostname, self.username, password,
                                     proxycmd):
                print("Could not send public key to {}".format(self.hostname))
                return

            # step 7: modify the ssh config file if necessary
            if not self.is_in_config():
                self._write_ssh_config(proxycmd=proxycmd)
            # TODO: add a check if new config is different from the current one. If so
            # infrom the user about it.

            # step 8: final check
            if self.can_login():
                self.setup_counter += 1
                print("Automatic ssh setup successful :-)")
                return
            else:
                print("Automatic ssh setup failed, sorry :-(")
                return

    def on_use_proxy_change(self, b):
        if self._use_proxy.value:
            self._proxy_ssh_box.layout.visibility = 'visible'
        else:
            self._proxy_ssh_box.layout.visibility = 'hidden'
            self._use_diff_proxy_username.value = False

    def on_use_diff_proxy_username_change(self, b):
        if self._use_diff_proxy_username.value:
            self._proxy_user_password_box.layout.visibility = 'visible'
        else:
            self._proxy_user_password_box.layout.visibility = 'hidden'


# Keep this function only because it might be used later.
# What it does: looks inside .ssh/config file and loads computer setup from
# there (if present)
#     def _get_from_config(self, b):
#         config = parse_sshconfig(self.hostname)
#         if 'user' in config:
#             self._inp_username.value = config['user']
#         else:
#             self._inp_username.value = ''
#         if 'proxycommand' in config:
#             self._use_proxy.value = True
#             proxy = ''.join([ s for s in config['proxycommand'].split() if '@' in s])
#             username, hostname = proxy.split('@')
#             self._inp_proxy_address.value = hostname
#             if username != self.username:
#                 self._use_diff_proxy_username.value = True
#                 self.proxy_username = username
#         else:
#             self._use_proxy.value = False

    @property
    def __password(self):
        """Returning the password and immediately destroying it"""
        passwd = copy(self._inp_password.value)
        self._inp_password.value = ''
        return passwd

    @property
    def __proxy_password(self):
        """Returning the password and immediately destroying it"""
        passwd = copy(self._inp_proxy_password.value)
        self._inp_proxy_password.value = ''
        return passwd

    @property
    def hostname(self):
        if len(self._inp_computer_hostname.value.strip()
               ) == 0:  # check hostname
            return None
        else:
            return self._inp_computer_hostname.value

    @hostname.setter
    def hostname(self, hostname):
        self._inp_computer_hostname.value = hostname

    @property
    def username(self):
        """Loking for username in user's input and config file"""
        if len(self._inp_username.value.strip()
               ) == 0:  # if username provided by user
            if not self.hostname is None:
                config = parse_sshconfig(self.hostname)
                if 'user' in config:  # if username is present in the config file
                    return config['user']
            else:
                return None
        else:
            return self._inp_username.value

    @username.setter
    def username(self, username):
        self._inp_username.value = username

    @property
    def proxy_hostname(self):
        if len(self._inp_proxy_address.value.strip()) == 0:
            return None
        else:
            return self._inp_proxy_address.value

    @proxy_hostname.setter
    def proxy_hostname(self, proxy_hostname):
        self._use_proxy.value = True
        self._inp_proxy_address.value = proxy_hostname

    @property
    def proxy_username(self):
        if len(self._inp_proxy_username.value.strip()) == 0:
            return None
        else:
            return self._inp_proxy_username.value

    @proxy_username.setter
    def proxy_username(self, proxy_username):
        self._use_proxy.value = True
        self._use_diff_proxy_username.value = True
        self._inp_proxy_username.value = proxy_username


class AiidaComputerSetup(ipw.VBox):
    def __init__(self, **kwargs):
        from aiida.transports import Transport
        from aiida.schedulers import Scheduler
        style = {"description_width": "200px"}

        # list of widgets to be displayed
        self._btn_setup_comp = ipw.Button(description="Setup computer")
        self._btn_setup_comp.on_click(self._on_setup_computer)
        self._inp_computer_name = ipw.Text(
            value='',
            placeholder='Will only be used within AiiDA',
            description="AiiDA computer name:",
            layout=ipw.Layout(width="500px"),
            style=style)
        self._computer_hostname = ipw.Dropdown(
            description="Select among configured hosts:",
            layout=ipw.Layout(width="500px"),
            style=style)
        self._inp_computer_description = ipw.Text(
            value='',
            placeholder='No description (yet)',
            description="Computer description:",
            layout=ipw.Layout(width="500px"),
            style=style)
        self._computer_workdir = ipw.Text(
            value='/scratch/{username}/aiida_run',
            description="Workdir:",
            layout=ipw.Layout(width="500px"),
            style=style)
        self._computer_mpirun_cmd = ipw.Text(
            value='mpirun -n {tot_num_mpiprocs}',
            description="Mpirun command:",
            layout=ipw.Layout(width="500px"),
            style=style)
        self._computer_ncpus = ipw.IntText(
            value=12,
            step=1,
            description='Number of CPU(s) per node:',
            layout=ipw.Layout(width="270px"),
            style=style)
        self._transport_type = ipw.Dropdown(
            value='ssh',
            options=Transport.get_valid_transports(),
            description="Transport type:",
            style=style)
        self._scheduler = ipw.Dropdown(
            value='slurm',
            options=Scheduler.get_valid_schedulers(),
            description="Scheduler:",
            style=style)
        self._prepend_text = ipw.Textarea(
            placeholder='Text to prepend to each command execution',
            description='Prepend text:',
            layout=ipw.Layout(width="400px"))
        self._append_text = ipw.Textarea(
            placeholder='Text to append to each command execution',
            description='Append text:',
            layout=ipw.Layout(width="400px"))
        self._btn_test = ipw.Button(description="Test computer")
        self._btn_test.on_click(self.test)

        self._setup_comp_out = ipw.Output(layout=ipw.Layout(width="500px"))
        self._test_out = ipw.Output(layout=ipw.Layout(width="500px"))

        # getting the list of available computers
        self.get_available_computers()

        # Check if some settings were already provided
        self._predefine_settings(**kwargs)
        children = [
            ipw.HBox([
                ipw.VBox([
                    self._inp_computer_name, self._computer_hostname,
                    self._inp_computer_description, self._computer_workdir,
                    self._computer_mpirun_cmd, self._computer_ncpus,
                    self._transport_type, self._scheduler
                ]),
                ipw.VBox([self._prepend_text, self._append_text])
            ]),
            ipw.HBox([self._btn_setup_comp, self._btn_test]),
            ipw.HBox([self._setup_comp_out, self._test_out]),
        ]
        super(AiidaComputerSetup, self).__init__(children, **kwargs)

    def _predefine_settings(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(
                    "'{}' object has no attribute '{}'".format(self, key))

    def get_available_computers(self, b=None):
        fn = path.expanduser("~/.ssh/config")
        if not path.exists(fn):
            return []
        cfglines = open(fn).readlines()
        self._computer_hostname.options = [
            line.split()[1] for line in cfglines if 'Host' in line
        ]

    def _configure_computer(self):
        """create AuthInfo"""
        print("Configuring '{}'".format(self.name))
        sshcfg = parse_sshconfig(self.hostname)
        authparams = {
            'compress': True,
            'gss_auth': False,
            'gss_deleg_creds': False,
            'gss_host': self.hostname,
            'gss_kex': False,
            'key_policy': 'WarningPolicy',
            'load_system_host_keys': True,
            'port': 22,
            'timeout': 60,
        }
        if 'user' in sshcfg:
            authparams['username'] = sshcfg['user']
        else:
            print(
                "SSH username is not provided, please run `verdi computer configure {}` "
                "from the command line".format(self.name))
            return
        if 'proxycommand' in sshcfg:
            authparams['proxy_command'] = sshcfg['proxycommand']
        aiidauser = User.objects.get_default()
        from aiida.orm import AuthInfo
        authinfo = AuthInfo(computer=Computer.objects.get(name=self.name), user=aiidauser)
        authinfo.set_auth_params(authparams)
        authinfo.store()
        print(check_output(['verdi', 'computer', 'show', self.name]))

    def _on_setup_computer(self, b):
        with self._setup_comp_out:
            clear_output()
            if self.name is None:  # check hostname
                print("Please specify the computer name (for AiiDA)")
                return
            try:
                computer = Computer.objects.get(name=self.name)
                print("A computer called {} already exists.".format(self.name))
                return
            except NotExistent:
                pass

            print("Creating new computer with name '{}'".format(self.name))
            computer = Computer(name=self.name, hostname=self.hostname, description=self.description)
            computer.set_transport_type(self.transport_type)
            computer.set_scheduler_type(self.scheduler)
            computer.set_workdir(self.workdir)
            computer.set_mpirun_command(self.mpirun_cmd.split())
            computer.set_default_mpiprocs_per_machine(self.ncpus)
            if self._prepend_text.value:
                computer.set_prepend_text(self.prepend_text)
            if self._append_text.value:
                computer.set_append_text(self.append_text)
            computer.store()
            self._configure_computer()

    def test(self, b=None):
        with self._test_out:
            clear_output()
            print(
                check_output(
                    ['verdi', 'computer', 'test', '--print-traceback', self.name]))

    @property
    def name(self):
        if len(self._inp_computer_name.value.strip()) == 0:  # check hostname
            return None
        else:
            return self._inp_computer_name.value

    @name.setter
    def name(self, name):
        self._inp_computer_name.value = name

    @property
    def hostname(self):
        if self._computer_hostname.value is None or len(
                self._computer_hostname.value.strip()) == 0:  # check hostname
            return None
        else:
            return self._computer_hostname.value

    @hostname.setter
    def hostname(self, hostname):
        if hostname in self._computer_hostname.options:
            self._computer_hostname.value = hostname

    @property
    def description(self):
        return self._inp_computer_description.value

    @description.setter
    def description(self, description):
        self._inp_computer_description.value = description

    @property
    def workdir(self):
        return self._computer_workdir.value

    @workdir.setter
    def workdir(self, workdir):
        self._computer_workdir.value = workdir

    @property
    def mpirun_cmd(self):
        return self._computer_mpirun_cmd.value

    @mpirun_cmd.setter
    def mpirun_cmd(self, mpirun_cmd):
        self._computer_mpirun_cmd.value = mpirun_cmd

    @property
    def ncpus(self):
        return self._computer_ncpus.value

    @ncpus.setter
    def ncpus(self, ncpus):
        self._computer_ncpus.value = int(ncpus)

    @property
    def transport_type(self):
        return self._transport_type.value

    @transport_type.setter
    def transport_type(self, transport_type):
        if transport_type in self._transport_type.options:
            self._transport_type.value = transport_type

    @property
    def scheduler(self):
        return self._scheduler.value

    @scheduler.setter
    def scheduler(self, scheduler):
        if scheduler in self._scheduler.options:
            self._scheduler.value = scheduler

    @property
    def prepend_text(self):
        return self._prepend_text.value

    @prepend_text.setter
    def prepend_text(self, prepend_text):
        self._prepend_text.value = prepend_text

    @property
    def append_text(self):
        return self._append_text.value

    @append_text.setter
    def append_text(self, append_text):
        self._append_text.value = append_text


class ComputerDropdown(ipw.VBox):
    def __init__(self, text='Select computer:', **kwargs):
        """ Dropdown for Codes for one input plugin.

        :param text: Text to display before dropdown
        :type text: str
        """

        self._dropdown = ipw.Dropdown(options=[],
                                      description=text,
                                      style={'description_width': 'initial'},
                                      disabled=True)
        self._btn_refresh = ipw.Button(description="Refresh",
                                       layout=ipw.Layout(width="70px"))

        self._setup_another = ipw.HTML(
            value=
            """<a href=./setup_computer.ipynb target="_blank">Setup new computer</a>""",
            layout={'margin': '0px 0px 0px 250px'})
        self._btn_refresh.on_click(self._refresh)
        self.output = ipw.Output()

        children = [
            ipw.HBox([self._dropdown, self._btn_refresh]), self._setup_another,
            self.output
        ]

        super(ComputerDropdown, self).__init__(children=children, **kwargs)

        self._refresh()

    def _get_computers(self):
        from aiida.orm.querybuilder import QueryBuilder
        current_user = User.objects.get_default()

        qb = QueryBuilder()
        qb.append(Computer,
                  project=['*'],
                  tag='computer')

        results = qb.all()

        # only computers configured for the current user
        results = [r for r in results if r[0].is_user_configured(current_user)]

        self._dropdown.options = {r[0].name: r[0] for r in results}

    def _refresh(self, b=None):
        with self.output:
            clear_output()
            self._get_computers()
            if not self.computers:
                print("No computers found.")
                self._dropdown.disabled = True
            else:
                self._dropdown.disabled = False

    @property
    def computers(self):
        return self._dropdown.options

    @property
    def selected_computer(self):
        try:
            return self._dropdown.value
        except KeyError:
            return None

    @selected_computer.setter
    def selected_computer(self, selected_computer):
        if selected_computer in self.computers:
            self._dropdown.label = selected_computer
