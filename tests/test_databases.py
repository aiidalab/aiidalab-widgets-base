import ase

import aiidalab_widgets_base as awb


def test_cod_query_widget():
    """Test the COD query widget."""

    widget = awb.CodQueryWidget()

    # Enter the query string.
    widget.inp_elements.value = "Ni Ti"

    # Run the query.
    widget._on_click_query()

    # Select one of the results.
    # TODO: Select a different structure to get rid of the ASE warning:
    # "ase/io/cif.py:401: UserWarning: crystal system 'cubic' is not interpreted
    # for space group 'Pm-3m'. This may result in wrong setting!"
    widget.drop_structure.label = "NiTi (id: 1100132)"

    # Check that the structure was loaded.
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "NiTi"


def test_optimade_query_widget():
    """Test the OPTIMADE query widget."""

    widget = awb.OptimadeQueryWidget()

    # At the present state I cannot check much. Most of the variables are locals of the  __init__ method.

    assert widget.structure is None


def test_computational_resources_database_widget():
    """Test the structure browser widget."""

    # Initiate the widget with no arguments.
    widget = awb.databases.ComputationalResourcesDatabaseWidget()
    assert "merlin.psi.ch" in widget.database

    # Initialize the widget with default_calc_job_plugin="cp2k"
    widget = awb.databases.ComputationalResourcesDatabaseWidget(
        default_calc_job_plugin="cp2k"
    )
    assert (
        "merlin.psi.ch" not in widget.database
    )  # Merlin does not have CP2K installed.

    widget.inp_domain.label = "daint.cscs.ch"
    widget.inp_computer.value = "multicore"
    widget.inp_code.value = "cp2k-9.1-multicore"

    # Check that the configuration is provided.

    assert "label" in widget.computer_setup["setup"]
    assert "hostname" in widget.ssh_config
    assert "filepath_executable" in widget.code_setup

    # Simulate reset.
    widget._reset()

    assert widget.computer_setup == {}
    assert widget.code_setup == {}
    assert widget.ssh_config == {}
