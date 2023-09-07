import pytest


@pytest.mark.usefixtures("aiida_profile_clean")
def test_computaional_resources_widget(aiida_local_code_bash):
    """Test the ComputationalResourcesWidget."""
    import aiidalab_widgets_base as awb

    widget = awb.ComputationalResourcesWidget(default_calc_job_plugin="bash")

    # Get the list of currently installed codes.
    codes_dict = widget._get_codes()
    assert "bash@localhost" in codes_dict


@pytest.mark.usefixtures("aiida_profile_clean")
def test_ssh_computer_setup_widget():
    """Test the SshComputerSetup."""
    from aiidalab_widgets_base.computational_resources import SshComputerSetup

    widget = SshComputerSetup()

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
    widget._write_ssh_config()
    assert widget._is_in_config()

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
def test_aiida_computer_setup_widget():
    """Test the AiidaComputerSetup."""
    from aiida import orm

    from aiidalab_widgets_base.computational_resources import AiidaComputerSetup

    widget = AiidaComputerSetup()

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
    from aiida.orm import load_computer

    from aiidalab_widgets_base.computational_resources import AiidaComputerSetup

    widget = AiidaComputerSetup()

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
    computer = load_computer("localhosttest")
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
    from aiida import orm

    from aiidalab_widgets_base.computational_resources import AiidaCodeSetup

    widget = AiidaCodeSetup()

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
    import aiidalab_widgets_base as awb

    widget = awb.ComputerDropdownWidget()

    assert "localhost" in widget.computers

    # Simulate selecting "localhost" in the dropdown menu.
    widget._dropdown.label = "localhost"
    assert widget.value == aiida_localhost.uuid

    # Trying to set the dropdown value to None
    widget.value = None
    assert widget._dropdown.value is None
