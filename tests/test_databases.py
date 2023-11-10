import ase
import pytest

import aiidalab_widgets_base as awb
from aiidalab_widgets_base.databases import ComputationalResourcesDatabaseWidget


# timeout for the test
@pytest.mark.timeout(30)
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
    widget = ComputationalResourcesDatabaseWidget()
    assert "daint.cscs.ch" in widget.database

    # Initialize the widget with default_calc_job_plugin="cp2k"
    # Note: after migrate to the new database with schema fixed, this test should go with
    # the local defined database rather than relying on the remote one.
    # Same for the quick setup widget.
    widget = ComputationalResourcesDatabaseWidget(default_calc_job_plugin="cp2k")
    assert (
        "merlin.psi.ch" not in widget.database
    )  # Merlin does not have CP2K installed.

    # Select computer/code
    widget.domain_selector.value = "daint.cscs.ch"
    widget.computer_selector.value = "mc"

    # check the code is not selected
    assert widget.code_selector.value is None

    widget.code_selector.value = "cp2k-9.1"

    # Check that the configuration is provided.
    assert "label" in widget.computer_setup
    assert "hostname" in widget.computer_configure
    assert "filepath_executable" in widget.code_setup

    # test after computer re-select to another, the code selector is reset
    widget.computer_selector.value = "gpu"
    assert widget.code_selector.value is None

    # Simulate reset.
    widget.reset()

    assert widget.computer_setup == {}
    assert widget.computer_configure == {}
    assert widget.code_setup == {}

    # after reset, the computer/code selector is reset
    assert widget.computer_selector.options == ()
    assert widget.code_selector.options == ()
    assert widget.computer_selector.value is None
    assert widget.code_selector.value is None

    # after reset, the domain selector value is reset, but the options are not
    assert widget.domain_selector.value is None
    assert len(widget.domain_selector.options) > 0


def test_resource_database_widget_recognize_template_entry_points():
    """Test that the template like entry points are recognized."""
    # Initiate the widget with no arguments.
    widget = ComputationalResourcesDatabaseWidget()
    assert "daint.cscs.ch" in widget.database

    # Initialize the widget with default_calc_job_plugin="quantumespresso.pw"
    # In merlin, there is a template entry point for Quantum ESPRESSO.
    # Note: after migrate to the new database with schema fixed, this test should go with
    # the local defined database rather than relying on the remote one.
    # Same for the quick setup widget.
    widget = ComputationalResourcesDatabaseWidget(
        default_calc_job_plugin="quantumespresso.pw"
    )
    assert "merlin.psi.ch" in widget.database

    widget = ComputationalResourcesDatabaseWidget(
        default_calc_job_plugin="quantumespresso.ph"
    )
    assert "merlin.psi.ch" in widget.database
