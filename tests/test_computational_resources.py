import pytest
from aiida import orm

from aiidalab_widgets_base import computational_resources


@pytest.mark.usefixtures("aiida_profile_clean")
def test_computational_resources_widget(aiida_local_code_bash):
    """Test the ComputationalResourcesWidget."""
    widget = computational_resources.ComputationalResourcesWidget(
        default_calc_job_plugin="bash"
    )

    # Get the list of currently installed codes.
    codes = widget._get_codes()
    assert "bash@localhost" == codes[0][0]


@pytest.mark.usefixtures("aiida_profile_clean")
def test_ssh_computer_setup_widget(monkeypatch, tmp_path):
    """Test the SshComputerSetup."""
    # mock home directory for ssh config file
    monkeypatch.setenv("HOME", str(tmp_path))
    widget = computational_resources.SshComputerSetup()

    ssh_config = {
        "hostname": "daint.cscs.ch",
        "port": 22,
        "proxy_jump": "ela.cscs.ch",
    }

    # At the beginning, the ssh_config should be an empty dictionary.
    assert widget.ssh_config == {}

    # Update the ssh_config that should also update the corresponding text fields in the widget.
    widget.ssh_config = ssh_config
    assert widget.hostname.value == "daint.cscs.ch"
    assert widget.port.value == 22
    assert widget.proxy_jump.value == "ela.cscs.ch"

    # Update the remaining text fields.
    widget.username.value = "aiida"

    # Write the information to ~/.ssh/config and check that it is there.
    assert widget._is_in_config() is False
    widget._write_ssh_config()
    assert widget._is_in_config() is True

    # Check that ssh-keygen operation is successful.
    widget._ssh_keygen()

    # Create non-default private key file.
    fpath = widget._add_private_key("my_key_name", b"my_key_content")
    assert fpath.exists()
    with open(fpath) as f:
        assert f.read() == "my_key_content"

    # Setting the ssh_config to an empty dictionary should reset the widget.
    widget.ssh_config = {}
    assert widget.hostname.value == ""
    assert widget.port.value == 22
    assert widget.proxy_jump.value == ""
    assert widget.username.value == ""
    assert widget._is_in_config() is False


@pytest.mark.usefixtures("aiida_profile_clean")
def test_aiida_computer_setup_widget(monkeypatch):
    """Test the AiidaComputerSetup."""
    # monkeypatch the parse_sshconfig
    monkeypatch.setattr(
        "aiida.transports.plugins.ssh.parse_sshconfig",
        lambda _: {"hostname": "daint.cscs.ch", "user": "aiida"},
    )
    widget = computational_resources.AiidaComputerSetup()

    # At the beginning, the computer_name should be an empty string.
    assert widget.label.value == ""

    # Preparing the computer setup.
    computer_setup = {
        "setup": {
            "label": "daint",
            "hostname": "daint.cscs.ch",
            "description": "Daint supercomputer",
            "work_dir": "/scratch/snx3000/{username}/aiida_run",
            "mpirun_command": "srun -n {tot_num_mpiprocs}",
            "default_memory_per_machine": 2000000000,
            "mpiprocs_per_machine": 12,
            "transport": "core.ssh",
            "scheduler": "core.slurm",
            "shebang": "#!/bin/bash",
            "use_double_quotes": True,
            "prepend_text": "#SBATCH --account=proj20",
            "append_text": "",
        },
        "configure": {
            "proxy_jump": "ela.cscs.ch",
            "safe_interval": 10,
            "use_login_shell": True,
        },
    }

    widget.computer_setup = computer_setup
    assert widget.on_setup_computer()

    # Check that the computer is created.
    computer = orm.load_computer("daint")
    assert computer.label == "daint"
    assert computer.hostname == "daint.cscs.ch"

    # Reset the widget and check that a few attributes are reset.
    widget.computer_setup = {}
    assert widget.label.value == ""
    assert widget.hostname.value == ""
    assert widget.description.value == ""

    # Check that setup is failing if the configuration is missing.
    assert not widget.on_setup_computer()
    assert widget.message.startswith("Please specify the computer name")


@pytest.mark.usefixtures("aiida_profile_clean")
def test_aiida_localhost_setup_widget():
    """Test the AiidaComputerSetup with core.local Trasport."""
    widget = computational_resources.AiidaComputerSetup()

    # At the beginning, the computer_name should be an empty string.
    assert widget.label.value == ""

    # Preparing the computer setup.
    computer_setup = {
        "setup": {
            "label": "localhosttest",
            "hostname": "localhost",
            "description": "locahost computer",
            "work_dir": "/home/jovyan/aiida_run",
            "mpirun_command": "srun -n {tot_num_mpiprocs}",
            "default_memory_per_machine": 2000000000,
            "mpiprocs_per_machine": 2,
            "transport": "core.local",
            "scheduler": "core.direct",
            "shebang": "#!/bin/bash",
            "use_double_quotes": True,
            "prepend_text": "",
            "append_text": "",
        },
        "configure": {
            "safe_interval": 10,
            "use_login_shell": True,
        },
    }

    widget.computer_setup = computer_setup
    assert widget.on_setup_computer()

    # Check that the computer is created.
    computer = orm.load_computer("localhosttest")
    assert computer.label == "localhosttest"
    assert computer.hostname == "localhost"

    # Reset the widget and check that a few attributes are reset.
    widget.computer_setup = {}
    assert widget.label.value == ""
    assert widget.hostname.value == ""
    assert widget.description.value == ""


@pytest.mark.usefixtures("aiida_profile_clean")
def test_aiida_code_setup(aiida_localhost):
    """Test the AiidaCodeSetup."""
    widget = computational_resources.AiidaCodeSetup()

    # At the beginning, the code_name should be an empty string.
    assert widget.label.value == ""

    # Preparing the code setup.
    code_setup = {
        "label": "bash",
        "computer": "localhost",
        "description": "Bash interpreter",
        "filepath_executable": "/bin/bash",
        "prepend_text": "",
        "append_text": "",
        "default_calc_job_plugin": "core.arithmetic.add",
    }

    widget.code_setup = code_setup
    # Make sure no warning message is displayed.
    assert widget.message == ""

    assert widget.on_setup_code()

    # Check that the code is created.
    code = orm.load_code("bash@localhost")
    assert code.label == "bash"
    assert code.description == "Bash interpreter"
    assert str(code.filepath_executable) == "/bin/bash"
    assert code.get_input_plugin_name() == "core.arithmetic.add"

    # Reset the widget and check that a few attributes are reset.
    widget.code_setup = {}
    assert widget.label.value == ""
    assert widget.computer.value is None
    assert widget.description.value == ""
    assert widget.filepath_executable.value == ""
    assert widget.prepend_text.value == ""
    assert widget.append_text.value == ""


@pytest.mark.usefixtures("aiida_profile_clean")
def test_computer_dropdown_widget(aiida_localhost):
    """Test the ComputerDropdownWidget."""
    widget = computational_resources.ComputerDropdownWidget()

    assert "localhost" in widget.computers

    # Simulate selecting "localhost" in the dropdown menu.
    widget._dropdown.label = "localhost"
    assert widget.value == aiida_localhost.uuid

    # Trying to set the dropdown value to None
    widget.value = None
    assert widget._dropdown.value is None


def test_template_variables_widget():
    """Test template_variables_widget."""
    w = computational_resources.TemplateVariablesWidget()

    w.templates = {
        "label": "{{ label }}",
        "hostname": "daint.cscs.ch",
        "description": "Piz Daint supercomputer at CSCS Lugano, Switzerland, multicore partition.",
        "transport": "core.ssh",
        "scheduler": "core.slurm",
        "work_dir": "/scratch/snx3000/{username}/aiida_run/",
        "shebang": "#!/bin/bash",
        "mpirun_command": "srun -n {tot_num_mpiprocs}",
        "mpiprocs_per_machine": 36,
        "prepend_text": "#SBATCH --partition={{ slurm_partition }}\n#SBATCH --account={{ slurm_account }}\n#SBATCH --constraint=mc\n#SBATCH --cpus-per-task=1\n\nexport OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK\nsource $MODULESHOME/init/bash\nulimit -s unlimited",
        "metadata": {
            "slurm_partition": {
                "type": "text",
                "key_display": "Slurm partition",
            },
        },
    }

    # Fill the template variables
    for key, value in w._template_variables.items():
        if key == "label":
            sub_widget = value.widget
            sub_widget.value = "daint-mc-test"

            # check the filled value is updated in the filled template
            assert w.filled_templates["label"] == "daint-mc-test"

    # Fill two template variables in one template line
    for key, value in w._template_variables.items():
        if key == "slurm_partition":
            sub_widget = value.widget
            sub_widget.value = "normal-test"

        elif key == "slurm_account":
            sub_widget = value.widget
            sub_widget.value = "newuser"

    # check the filled value is updated in the filled template
    assert (
        w.filled_templates["prepend_text"]
        == "#SBATCH --partition=normal-test\n#SBATCH --account=newuser\n#SBATCH --constraint=mc\n#SBATCH --cpus-per-task=1\n\nexport OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK\nsource $MODULESHOME/init/bash\nulimit -s unlimited"
    )

    # Test the filled template is updated when the filled value is updated.
    for key, value in w._template_variables.items():
        if key == "slurm_partition":
            sub_widget = value.widget
            sub_widget.value = "debug"

    assert "debug" in w.filled_templates["prepend_text"]


def test_template_variables_widget_metadata():
    """Test metadata support in template_variables_widget."""
    w = computational_resources.TemplateVariablesWidget()

    w.templates = {
        "prepend_text": "#SBATCH --partition={{ slurm_partition }}\n#SBATCH --account={{ slurm_account }}\n#SBATCH --constraint=mc\n#SBATCH --cpus-per-task=1\n\nexport OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK\nsource $MODULESHOME/init/bash\nulimit -s unlimited",
        "metadata": {
            "slurm_partition": {
                "type": "list",
                "default": "normal",
                "options": ["normal", "normal-test", "debug"],
                "key_display": "Slurm partition",
            },
            "slurm_account": {
                "type": "text",
                "key_display": "Slurm account",
            },
        },
    }

    # Fill two template variables in one template line
    for key, value in w._template_variables.items():
        if key == "slurm_partition":
            sub_widget = value.widget

            # Test set the widget from the metadata
            assert sub_widget.description == "Slurm partition"
            assert sub_widget.options == ("normal", "normal-test", "debug")
            assert sub_widget.value == "normal"

            sub_widget.value = "normal-test"

        elif key == "slurm_account":
            sub_widget = value.widget
            sub_widget.value = "newuser"

    # check the filled value is updated in the filled template
    assert (
        w.filled_templates["prepend_text"]
        == "#SBATCH --partition=normal-test\n#SBATCH --account=newuser\n#SBATCH --constraint=mc\n#SBATCH --cpus-per-task=1\n\nexport OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK\nsource $MODULESHOME/init/bash\nulimit -s unlimited"
    )
    assert "metadata" not in w.filled_templates


def test_template_variables_widget_multi_template_variables():
    """This is the test for same key in multiple templates."""
    w = computational_resources.TemplateVariablesWidget()

    w.templates = {
        "label": "{{ code_binary_name }}-7.2",
        "description": "The code {{ code_binary_name }}.x of Quantum ESPRESSO compiled for daint-mc",
        "default_calc_job_plugin": "quantumespresso.{{ code_binary_name }}",
        "filepath_executable": "/apps/dom/UES/jenkins/7.0.UP03/21.09/dom-mc/software/QuantumESPRESSO/7.0-CrayIntel-21.09/bin/{{ code_binary_name }}.x",
        "prepend_text": "module load daint-mc\nmodule load QuantumESPRESSO\n",
        "append_text": "",
        "metadata": {
            "code_binary_name": {
                "type": "list",
                "options": ["pw", "ph", "pp"],
                "key_display": "Code name",
            },
        },
    }

    # Fill the code_binary_name template variables for all
    for key, value in w._template_variables.items():
        if key == "code_binary_name":
            sub_widget = value.widget
            assert sub_widget.description == "Code name"
            assert sub_widget.options == ("pw", "ph", "pp")
            assert sub_widget.value is None

            sub_widget.value = "ph"

    # check all filed templates are updated
    assert w.filled_templates["label"] == "ph-7.2"
    assert (
        w.filled_templates["description"]
        == "The code ph.x of Quantum ESPRESSO compiled for daint-mc"
    )
    assert w.filled_templates["default_calc_job_plugin"] == "quantumespresso.ph"


def test_template_variables_widget_help_text_disappear_if_no_template_str():
    """This test when the template string is update to without template field, the help text should disappear."""
    w = computational_resources.TemplateVariablesWidget()

    # The initial help text should be not displayed.
    assert w._help_text.layout.display == "none"

    w.templates = {
        "label": "{{ code_binary_name }}-7.2",
    }

    # The help text should be displayed.
    assert w._help_text.layout.display == "block"

    # Fill the code_binary_name template variables for all
    for key, value in w._template_variables.items():
        if key == "code_binary_name":
            sub_widget = value.widget
            sub_widget.value = "pw"

    w.templates = {
        "label": "ph-7.2",
    }
    # The help text should be not displayed.
    assert w._help_text.layout.display == "none"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_quick_setup_widget():
    """Test the QuickSetupWidget."""
    from aiidalab_widgets_base.computational_resources import QuickSetupWidget

    w = QuickSetupWidget()

    # Test message is update correctly. By click setup button without filling in any information.
    w._on_quick_setup()

    assert "Please specify the computer name" in w.message

    # Test select a new resource setup will update the output interface (e.g. ssh_config, computer_setup, code_setup)
    # and the computer/code setup widget will be updated accordingly.
    w.comp_resources_database.domain_selector.value = "daint.cscs.ch"
    w.comp_resources_database.computer_selector.value = "mc"
    w.comp_resources_database.code_selector.value = "QE-7.2-exe-template"

    assert w.ssh_config == w.comp_resources_database.ssh_config
    assert w.computer_setup == w.comp_resources_database.computer_setup
    assert w.code_setup == w.comp_resources_database.code_setup

    # Trigger the setup button again, since the computer name is filled in (this test computer/code setup widget is updated),
    # the message should be updated.
    w._on_quick_setup()

    assert "Please fill missing variable" in w.message

    # Fill in the computer name and trigger the setup button again, the message should be updated.
    for (
        key,
        mapping_variable,
    ) in w.template_variables_computer._template_variables.items():
        if key == "label":
            sub_widget = mapping_variable.widget

            # Test the default value is filled in correctly.
            assert sub_widget.value == "daint-mc"
        if key == "slurm_partition":
            sub_widget = mapping_variable.widget
            sub_widget.value = "debug"
        if key == "slurm_account":
            sub_widget = mapping_variable.widget
            sub_widget.value = "newuser"

    # Fill the code name
    for key, mapping_variable in w.template_variables_code._template_variables.items():
        if key == "code_binary_name":
            sub_widget = mapping_variable.widget
            sub_widget.value = "ph"

            # select the other code and check the filled template is updated
            sub_widget.value = "pw"

    w.ssh_computer_setup.username.value = "aiida"

    # import ipdb; ipdb.set_trace()

    w._on_quick_setup()

    assert "created" in w.message
    assert "pw" in w.message
    assert w.success

    # test select new resource reset the widget, success trait, and message trait.
    w.comp_resources_database.reset()

    assert w.ssh_config == {}
    assert w.computer_setup == {}
    assert w.code_setup == {}
    assert w.success is False
    assert w.message == ""
    assert w.template_variables_code._help_text.layout.display == "none"
    assert w.template_variables_code._template_variables == {}

    # reselect after reset should update the output interface
    w.comp_resources_database.domain_selector.value = "daint.cscs.ch"
    assert w.template_variables_computer._template_variables != {}


@pytest.mark.usefixtures("aiida_profile_clean")
def test_quick_setup_widget_computer_change_code_reset():
    """Test the QuickSetupWidget that when computer template changed, the code selector widget is reset."""
    from aiidalab_widgets_base.computational_resources import QuickSetupWidget

    w = QuickSetupWidget()

    # Test select a new resource setup will update the output interface (e.g. ssh_config, computer_setup, code_setup)
    # and the computer/code setup widget will be updated accordingly.
    w.comp_resources_database.domain_selector.value = "daint.cscs.ch"
    w.comp_resources_database.computer_selector.value = "mc"
    w.comp_resources_database.code_selector.value = "QE-7.2-exe-template"

    assert w.template_variables_code._help_text.layout.display == "block"

    # Change the computer template, code template prompt box should stay.
    w.comp_resources_database.computer_selector.value = "gpu"

    # check the option of resource database widget is reset
    assert w.comp_resources_database.code_selector.value is None


@pytest.mark.usefixtures("aiida_profile_clean")
def test_bundle_resource_setup_widget():
    """This is the bundle test of the resource setup widget specifically to DetailedSetupWidget.
    Since the DetailedSetupWidget is a container widget, it is meaningless to test it independently.
    """
    from aiidalab_widgets_base.computational_resources import (
        ComputationalResourcesWidget,
    )

    # Set with clear_after=1 to avoid the widget frozen at the end of test to wait the counting thread to finish.
    w = ComputationalResourcesWidget(clear_after=1)

    # go last step to setup code withou computer setup
    w_quick = w.quick_setup
    w_detailed = w.detailed_setup

    w_quick.comp_resources_database.domain_selector.value = "daint.cscs.ch"
    w_quick.comp_resources_database.computer_selector.value = "mc"
    w_quick.comp_resources_database.code_selector.value = "pw-7.0"

    # Check that the computer/code setup widget is updated accordingly in the detailed setup widget.
    # By triggering the setup button one by one in the detailed setup widget, the message should be updated.
    computer_label = "daint-mc"
    w_detailed.aiida_computer_setup.label.value = computer_label
    w_detailed.aiida_computer_setup.on_setup_computer()

    assert "created" in w_detailed.message

    comp_uuid = orm.load_computer(computer_label).uuid
    w_detailed.aiida_code_setup.computer._dropdown.value = comp_uuid
    w_detailed.aiida_code_setup.on_setup_code()

    assert "created" in w_detailed.message

    # test select new resource reset the widget, success trait, and message trait, and the computer/code setup widget is cleared.
    w_quick.comp_resources_database.reset()

    assert w_detailed.aiida_computer_setup.computer_setup == {}
    assert w_detailed.aiida_code_setup.code_setup == {}
    assert w_detailed.ssh_computer_setup.ssh_config == {}
    assert w_detailed.success is False
    assert w_detailed.message == ""
