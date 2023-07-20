from pathlib import Path

import ase
import numpy as np
import pytest

import aiidalab_widgets_base as awb


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_manager_widget(structure_data_object):
    """Test the `StructureManagerWidget`."""
    structure_manager_widget = awb.StructureManagerWidget(
        importers=[
            awb.StructureUploadWidget(title="From computer"),
        ],
        editors=[
            awb.BasicStructureEditor(title="Basic Editor"),
        ],
    )
    structure_manager_widget.input_structure = structure_data_object

    assert structure_manager_widget.structure is not None
    assert isinstance(structure_manager_widget.structure, ase.Atoms)

    # Test the structure periodicity
    assert structure_manager_widget.viewer.periodicity.value == "Periodicity: xyz"

    # Store structure and check that it is stored.
    structure_manager_widget.store_structure()
    assert structure_manager_widget.structure_node.is_stored
    assert structure_manager_widget.structure_node.pk is not None

    # Simulate the structure modification.
    new_structure = structure_manager_widget.structure.copy()
    new_structure[0].position += [0, 0, 1]

    structure_manager_widget.structure = new_structure
    assert not structure_manager_widget.structure_node.is_stored
    assert np.all(
        structure_manager_widget.structure[0].position == new_structure[0].position
    )

    # Undo the structure modification.
    structure_manager_widget.undo()
    assert np.any(
        structure_manager_widget.structure[0].position != new_structure[0].position
    )

    # test the widget can be instantiated with empty inputs
    structure_manager_widget = awb.StructureManagerWidget(
        importers=[
            awb.StructureUploadWidget(title="From computer"),
        ],
    )

    assert structure_manager_widget.structure is None


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_browser_widget(structure_data_object):
    """Test the `StructureBrowserWidget`."""
    structure_browser_widget = awb.StructureBrowserWidget()
    assert structure_browser_widget.structure is None

    structure_browser_widget.search()

    # There should be no structures in the database, only the default output "Select structure".
    assert len(structure_browser_widget.results.options) == 1

    # Store the structure and check that it is listed in the widget.
    structure_data_object.store()
    structure_browser_widget.search()
    assert len(structure_browser_widget.results.options) == 2

    # Simulate the structure selection.
    structure_browser_widget.results.value = structure_data_object

    assert structure_browser_widget.structure.uuid == structure_data_object.uuid


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_upload_widget():
    """Test the `StructureUploadWidget`."""
    widget = awb.StructureUploadWidget()
    assert widget.structure is None

    # Simulate the structure upload.
    widget._on_file_upload(
        change={
            "new": {
                "test.xyz": {
                    "content": b"""2

                Si 0.0 0.0 0.0
                Si 0.5 0.5 0.5
                """,
                }
            }
        }
    )
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "Si2"
    assert np.all(widget.structure[0].position == [0, 0, 0])


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_examples_widget():
    """Test the `StructureExamplesWidget`."""
    this_folder = Path(__file__).parent

    widget = awb.StructureExamplesWidget(
        examples=[
            (
                "Silicon oxide",
                this_folder / ".." / "miscellaneous" / "structures" / "SiO2.xyz",
            )
        ]
    )
    assert widget.structure is None

    # Simulate the structure selection.
    widget._select_structure.label = "Silicon oxide"
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "O4Si2"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_smiles_widget():
    """Test the `SmilesWidget`."""
    widget = awb.SmilesWidget()
    assert widget.structure is None

    # Simulate the structure generation.
    widget.smiles.value = "C"
    widget._on_button_pressed()
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "CH4"

    # Regression test that we can generate 1-atom and 2-atom molecules
    widget.smiles.value = "[O]"
    widget._on_button_pressed()
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "O"

    widget.smiles.value = "N#N"
    widget._on_button_pressed()
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "N2"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_basic_cell_editor_widget(structure_data_object):
    """Test the `BasicCellEditor`."""
    widget = awb.BasicCellEditor()
    assert widget.structure is None

    # Set the structure.
    widget.structure = structure_data_object.get_ase()
    assert widget.structure.get_chemical_formula() == "Si2"

    # Convert to conventional cell.
    widget._to_conventional_cell()
    assert widget.structure.get_chemical_formula() == "Si8"

    # Convert to primitive cell.
    widget._to_primitive_cell()
    assert widget.structure.get_chemical_formula() == "Si2"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_basic_structure_editor(structure_data_object):
    """Test the `BasicStructureEditor`."""
    widget = awb.BasicStructureEditor()
    assert widget.structure is None

    # Set the structure.
    widget.structure = structure_data_object.get_ase()

    # Set first action point vector to the first atom.
    widget.selection = [0]
    widget.def_axis_p1()
    assert widget.axis_p1.value == "0.0 0.0 0.0"

    # Set second action point vector to the second atom.
    widget.selection = [1]
    widget.def_axis_p2()
    assert widget.axis_p2.value == "1.92 1.11 0.79"

    # Move an atom.
    original_position = widget.structure[
        1
    ].position  # original position of the second atom
    widget.displacement.value = "1.5"  # displacement in Angstrom
    assert np.allclose(
        widget.action_vector, np.array([0.8164966, 0.47140451, 0.33333329]), atol=1e-2
    )
    widget.translate_dr()
    assert np.linalg.norm(widget.structure[1].position - original_position) - 1.5 < 1e-6

    # Move an atom to its original position.
    widget.selection = [1]
    widget.dxyz.value = "{:.8f} {:.8f} {:.8f}".format(*original_position)
    widget.translate_to_xyz()
    assert np.allclose(widget.structure[1].position, original_position)

    # Move an atom by a vector (1, 1, 1).
    widget.selection = [1]
    widget.dxyz.value = "1.0 1.0 1.0"
    widget.translate_dxdydz()
    assert np.allclose(
        widget.structure[1].position, original_position + np.array([1.0, 1.0, 1.0])
    )

    # Copy an atom.
    widget.selection = [1]
    widget.copy_sel()
    assert len(widget.structure) == 3

    # Delete an atom.
    widget.selection = [2]
    widget.remove()
    assert len(widget.structure) == 2

    # Add an atom.
    widget.selection = [1]
    widget.element.value = "C"
    widget.add()
    assert len(widget.structure) == 3
    assert widget.structure[2].symbol == "C"

    # Modify an atom.
    widget.selection = [1]
    widget.element.value = "O"
    widget.mod_element()
    assert widget.structure.get_chemical_formula() == "COSi"
