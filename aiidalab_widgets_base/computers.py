from __future__ import print_function

import pexpect
import ipywidgets as ipw

from os import path
from copy import copy
from IPython.display import clear_output
from subprocess import check_output, call

from aiida import load_dbenv, is_dbenv_loaded
from aiida.backends import settings
if not is_dbenv_loaded():
    load_dbenv(profile=settings.AIIDADB_PROFILE)

from aiida.orm import Computer
from aiida.common.exceptions import NotExistent
from aiida.transport.plugins.ssh import parse_sshconfig


class SshComputerSetup(ipw.VBox):
    def __init__(self):
        style = {"description_width":"200px"}
        computer_image = ipw.HTML('<img width="200px" src="./miscellaneous/images/computer.png">')
        self._inp_username = ipw.Text(description="Ssh username:", layout=ipw.Layout(width="350px"), style=style)
        self._inp_password = ipw.Password(description="Ssh password:", layout=ipw.Layout(width="350px"), style=style)
        self._btn_get_config = ipw.Button(description="Get from config", layout={'margin': '20px 0px 20px 130px'}, disabled=True)
        self._btn_get_config.on_click(self._get_from_config)
        # Computer ssh settings
        self._inp_computer_hostname = ipw.Text(description="Computer name:",
                                     layout=ipw.Layout(width="350px"),
                                     style=style)
        self._inp_computer_hostname.observe(self.on_computer_hostname_change, names='value')
        self._use_proxy = ipw.Checkbox(value=False, description='Use proxy')
        self._use_proxy.observe(self.on_use_proxy_change, names='value')
        computer_ssh_box = ipw.VBox([self._btn_get_config,
                                     self._inp_username,
                                     self._inp_password,
                                     self._use_proxy])

        # Proxy ssh settings
        self._inp_proxy_address = ipw.Text(description="Proxy server address:",
                                           layout=ipw.Layout(width="350px"),
                                           style=style)
        self._use_diff_proxy_username = ipw.Checkbox(value=False,
                                               description='Use different username and password',
                                               layout={'width': 'initial'})
        self._use_diff_proxy_username.observe(self.on_use_diff_proxy_username_change, names='value')

        self._inp_proxy_username = ipw.Text(value='',
                                            description="Proxy server username:",
                                            layout=ipw.Layout(width="350px"), style=style)
        self._inp_proxy_password = ipw.Password(value='',
                                                description="Proxy server password:",
                                                layout=ipw.Layout(width="350px"),
                                                style=style)
        self._proxy_user_password_box = ipw.VBox([self._inp_proxy_username,
                                                  self._inp_proxy_password],
                                                 layout={'visibility':'hidden'})
        self._proxy_ssh_box = ipw.VBox([self._inp_proxy_address,
                                        self._use_diff_proxy_username,
                                        self._proxy_user_password_box],
                                 layout = {'visibility':'hidden'})

        self._btn_setup_ssh = ipw.Button(description="Setup ssh")
        self._btn_setup_ssh.on_click(self.on_setup_ssh)
        self._setup_ssh_out = ipw.Output()

        super(SshComputerSetup, self).__init__([ipw.HBox([computer_image, ipw.VBox([self._inp_computer_hostname,
                                                                                    ipw.HBox([computer_ssh_box, self._proxy_ssh_box])
                                                                                   ])
                                                         ]),
                                                self._btn_setup_ssh,
                                                self._setup_ssh_out])

    def _ssh_keygen(self):
        fn = path.expanduser("~/.ssh/id_rsa")
        if not path.exists(fn):
            print("Creating ssh key pair")
            call(["ssh-keygen", "-f", fn, "-t", "rsa", "-N", ""]) # returns non-0 if the key pair already exists

    def is_host_known(self, hostname):
        fn = path.expanduser("~/.ssh/known_hosts")
        if not path.exists(fn):
            return False
        return call(["ssh-keygen", "-F", hostname]) == 0

    def make_host_known(self, hostname, proxycmd=[]):
        fn = path.expanduser("~/.ssh/known_hosts")
        print("Adding keys from %s to %s"%(hostname, fn))
        hashes = check_output(proxycmd+["ssh-keyscan", "-H", hostname])
        with open(fn, "a") as f:
            f.write(hashes)

    def can_login(self, hostname, username):
        userhost = username+"@"+hostname
        print("Trying ssh "+userhost+"... ", end='')
        ret = call(["ssh", userhost, "true"])
        print("Ok" if ret==0 else "Failed")
        return ret==0

    def _is_in_config(self, hostname):
        fn = path.expanduser("~/.ssh/config")
        if not path.exists(fn):
            return False
        cfglines = open(fn).read().split("\n")
        return "Host "+hostname in cfglines

    def _write_ssh_config(self, hostname, username, proxycmd):
        fn = path.expanduser("~/.ssh/config")
        print("Adding section to "+fn)
        with open(fn, "a") as f:
            f.write("Host "+hostname+"\n")
            f.write("User "+username+"\n")
            if proxycmd:
                f.write("ProxyCommand ssh -q -Y "+proxycmd+" netcat %h %p\n")
            f.write("ServerAliveInterval 5\n")

    def send_pubkey(self, hostname, username, password):
        print("Setting up password-free connection to {}... ".format(hostname),end='')
        str_ssh = 'ssh-copy-id %s@%s' %(username, hostname)
        child = pexpect.spawn(str_ssh)
        index = child.expect(['s password:', # 0 
                              'ERROR: No identities found', # 1
                              'All keys were skipped because they already exist on the remote system', # 2
                              'Could not resolve hostname', # 3
                              pexpect.EOF],timeout=10) # final
        if index == 0:
            child.sendline(password)
            try:
                child.expect("Now try logging into",timeout=5)
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
            print ("Failed")
            print ("Unknown problem")
            print (child.before, child.after)
            child.close()
            return False

    def _configure_proxy(self, password, proxy_password):
        # if proxy IS required
        if self._use_proxy.value:
            # again some standard checks if proxy server parameters are provided
            if len(self._inp_proxy_address.value.strip()) == 0: # hostname
                print("Please specify the proxy server username")
                return False, [], None
            # if proxy username and password must be different from the main computer - they should be provided
            if self._use_diff_proxy_username.value:
                # check username
                if self._inp_proxy_username.value: 
                    proxy_username = self._inp_proxy_username.value
                else:
                    print("Please specify the proxy server username")
                    return False, [], None
                # check password
                if not proxy_password:
                    print("Please specify the proxy server password")
                    return False, [], None
            else: # if username and password are the same as for the main computer
                proxy_username = self._inp_username.value
                proxy_password = password
            proxy = [proxy_username, self._inp_proxy_address.value]
            # make proxy server known
            if not self.is_host_known(self._inp_proxy_address.value):
                self.make_host_known(self._inp_proxy_address.value)
        # if proxy is NOT required
        else:
            proxy = []
        return True, proxy, proxy_password

    def on_setup_ssh(self, b):
        """CAUTION: modifying the order of operations in this function can lead to unexpected problems"""
        with self._setup_ssh_out:
            clear_output()
            self._ssh_keygen()

            #temporary passwords
            password = self.__password
            proxy_password = self.__proxy_password

            # standard checks that all the necessary data are provided
            if len(self._inp_computer_hostname.value.strip()) == 0: # check hostname
                print("Please specify the computer hostname")
                return
            if len(self._inp_username.value.strip()) == 0: # check username
                print("Please enter your ssh username")
                return
            if len(password.strip()) == 0: # check password
                print("Please enter your ssh password")
                return

            # get the right commands to access the proxy server
            success, proxy, proxy_password = self._configure_proxy(password, proxy_password)
            if not success:
                return       

            # modifying the ssh config file if necessary
            if not self._is_in_config(self._inp_computer_hostname.value):
                self._write_ssh_config(self._inp_computer_hostname.value,
                                       self._inp_username.value,
                                       '@'.join(proxy))

            # if password-free access is already enabled - nothing needs to be done
            if self.can_login(self._inp_computer_hostname.value, self._inp_username.value):
                print ("Password-free access is already enabled")
                return
            
            # sending public key to the proxy host
            if proxy:
                if not self.send_pubkey(proxy[1], proxy[0], proxy_password):
                    return
                proxycmd = ['ssh']+['@'.join(proxy)]
            else:
                proxycmd = []


            # make host known by ssh on the proxy server
            if not self.is_host_known(self._inp_computer_hostname.value):
                self.make_host_known(self._inp_computer_hostname.value, proxycmd)

            # sending publick key to the main host
            if not self.send_pubkey(self._inp_computer_hostname.value, self._inp_username.value, password):
                return

            # final check
            if self.can_login(self._inp_computer_hostname.value,  self._inp_username.value):
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
    
    def on_computer_hostname_change(self, b):
        if self._inp_computer_hostname.value:
            self._btn_get_config.disabled = False
        else:
            self._btn_get_config.disabled = True

    def _get_from_config(self, b):

        with self._setup_ssh_out:
            clear_output()
            config = parse_sshconfig(self._inp_computer_hostname.value)
            if 'user' in config:
                self._inp_username.value = config['user']
            else:
                self._inp_username.value = ''
            if 'proxycommand' in config:
                self._use_proxy.value = True
                proxy = ''.join([ s for s in config['proxycommand'].split() if '@' in s])
                username, hostname = proxy.split('@')
                self._inp_proxy_address.value = hostname
                if username != self._inp_username.value:
                    self._use_diff_proxy_username.value = True
                    self._inp_proxy_username.value = username
            else:
                self._use_proxy.value = False

    @property
    def __password(self):
        """Returning the password and destroying it"""
        passwd = copy(self._inp_password.value)
        self._inp_password.value = ''
        return passwd

    @property
    def __proxy_password(self):
        """Returning the password and destroying it"""
        passwd = copy(self._inp_proxy_password.value)
        self._inp_proxy_password.value = ''
        return passwd

    @property
    def hostname(self):
        return self._inp_computer_hostname.value
    
    @property
    def username(self):
        return self._inp_username.value


class AiidaComputerSetup(ipw.VBox):
    def __init__(self):
        from aiida.transport import Transport
        from aiida.scheduler import Scheduler
        style = {"description_width":"200px"}
        self._btn_setup_comp = ipw.Button(description="Setup Computer")
        self._btn_setup_comp.on_click(self._on_setup_computer)
        self._computer_name = ipw.Text(value='',
                                       placeholder='Will be only used within AiiDA',
                                       description="AiiDA computer name:",
                                       layout=ipw.Layout(width="500px"),
                                       style=style)
        self._computer_hostname = ipw.Dropdown(options=self._get_available_computers(),
                                               description="Select among the available hosts:",
                                               layout=ipw.Layout(width="500px"),
                                               style=style)
        self._inp_computer_description = ipw.Text(value='',
                                                  placeholder='No description (yet)',
                                                  description="Computer description:",
                                                  layout=ipw.Layout(width="500px"),
                                                  style=style)
        self._computer_workdir = ipw.Text(value='/scratch/{username}/aiida_run',
                                          description="Workdir:",
                                          layout=ipw.Layout(width="500px"),
                                          style=style)
        self._computer_mpirun_cmd = ipw.Text(value='mpirun -n {tot_num_mpiprocs}',
                                             description="Mpirun command:",
                                             layout=ipw.Layout(width="500px"),
                                             style=style)
        self._computer_ncpus = ipw.IntText(value=12,
                                           step=1,
                                           description='Number of CPU(s) per node:',
                                           layout=ipw.Layout(width="270px"),
                                           style=style)
        self._transport_type = ipw.Dropdown(value='ssh',
                                            options=Transport.get_valid_transports(),
                                            description="Transport type:",
                                            style=style)
        self._scheduler = ipw.Dropdown(value='slurm',
                                       options=Scheduler.get_valid_schedulers(),
                                       description="Scheduler:",
                                       style=style)
        self._prepend_text = ipw.Textarea(placeholder='Text to prepend to each command execution',
                                          description='Prepend text:',
                                          layout=ipw.Layout(width="400px")
                                         )
        self._append_text = ipw.Textarea(placeholder='Text to append to each command execution',
                                         description='Append text:',
                                         layout=ipw.Layout(width="400px")
                                        )
        self._setup_comp_out = ipw.Output()
        super(AiidaComputerSetup, self).__init__([ipw.HBox([ipw.VBox([self._computer_name,
                                                                      self._computer_hostname,
                                                                      self._inp_computer_description,
                                                                      self._computer_workdir,
                                                                      self._computer_mpirun_cmd,
                                                                      self._computer_ncpus,
                                                                      self._transport_type,
                                                                      self._scheduler]), ipw.VBox([self._prepend_text,
                                                                                                   self._append_text])]),
                                                  self._btn_setup_comp,
                                                  self._setup_comp_out])
    def _get_available_computers(self):
        fn = path.expanduser("~/.ssh/config")
        if not path.exists(fn):
            return False
        cfglines = open(fn).readlines()
        return [line.split()[1] for line in cfglines if 'Host' in line]

    def _configure_computer(self):
        """create DbAuthInfo"""
        sshcfg = parse_sshconfig(self._computer_hostname.value)
        authparams = {
            'compress': True,
            'gss_auth': False,
            'gss_deleg_creds': False,
            'gss_host': self._computer_hostname.value,
            'gss_kex': False,
            'key_policy': 'WarningPolicy',
            'load_system_host_keys': True,
            'port': 22,
            'timeout': 60,
        }
        if 'User' in sshcfg:
            authparams['username'] = sshcfg['User']
        else:
            print ("Ssh username is not provided, please run `verdi computer configure {}` "
                   "from the command line".format(self._computer_name.value))
            return
        if 'proxycommand' in sshcfg:
            authparams['proxy_command'] = sshcfg['proxycommand']
        aiidauser = get_automatic_user()
        authinfo = DbAuthInfo(dbcomputer=Computer.get(computer_name).dbcomputer, aiidauser=aiidauser)
        authinfo.set_auth_params(authparams)
        authinfo.save()
        call(['verdi', 'computer', 'show', self._computer_name.value])

    def _on_setup_computer(self, b):
        with self._setup_comp_out:
            clear_output()
            try:
                computer = Computer.get(self._computer_name.value)
                print("A computer called {} already exists.".format(self._computer_name.value))
                return
            except NotExistent:
                pass

            print("Creating new computer with name '{}'".format(self._computer_name.value))
            computer = Computer(name=self._computer_name.value)
            computer.set_hostname(self._computer_hostname.value)
            computer.set_description(self._inp_computer_description.value)
            computer.set_enabled_state(True)
            computer.set_transport_type(self._transport_type.value)
            computer.set_scheduler_type(self._scheduler.value)
            computer.set_workdir(self._computer_workdir.value)
            computer.set_mpirun_command(self._computer_mpirun_cmd.value.split())
            computer.set_default_mpiprocs_per_machine(self._computer_ncpus.value)
            if self._prepend_text.value:
                computer.set_prepend_text(prepend_text.value)
            if self._append_text.value:
                computer.set_append_text(append_text.value)
            computer.store()
            self._configure_computer()

class AiidaComputerTest(ipw.VBox):
    def on_test_computer(self, b):
        with self._test_out:
            clear_output()
            if len(inp_computer_name.value.strip())==0:
                print("Please enter computer name")
                return
        call(['verdi', 'computer', 'test', '--traceback', self._inp_computer_name.value])

    def __init__(self):
        self._test_out = ipw.Output()
        self._btn_test_comp = ipw.Button(description="Test Computer")
        self._btn_test_comp.on_click(self.on_test_computer)
        super(AiidaComputerTest, self).__init__([self._btn_test_comp])