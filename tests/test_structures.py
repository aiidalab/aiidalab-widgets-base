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
        input_structure=structure_data_object,
    )

    assert structure_manager_widget.structure is not None
    assert isinstance(structure_manager_widget.structure, ase.Atoms)

    # Test the structure periodicity
    assert structure_manager_widget.viewer.periodicity.value == "Periodicity: xyz"

    # Store structure and check that it is stored.
    structure_manager_widget.btn_store.click()
    assert structure_manager_widget.structure_node.is_stored
    assert structure_manager_widget.structure_node.pk is not None

    # Try to store the stored structure.
    structure_manager_widget.btn_store.click()
    assert "Already stored" in structure_manager_widget.output.value

    # Simulate the structure modification.
    new_structure = structure_manager_widget.structure.copy()
    new_structure[0].position += [0, 0, 1]

    structure_manager_widget.structure = new_structure
    assert not structure_manager_widget.structure_node.is_stored
    assert np.all(
        structure_manager_widget.structure[0].position == new_structure[0].position
    )

    # Store the modified structure.
    structure_manager_widget.btn_store.click()
    assert structure_manager_widget.structure_node.is_stored

    # Undo the structure modification.
    structure_manager_widget.undo()
    assert np.any(
        structure_manager_widget.structure[0].position != new_structure[0].position
    )
    structure_manager_widget.undo()  # Undo the structure creation.
    assert structure_manager_widget.structure is None


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_manager_widget_multiple_importers_editors(structure_data_object):
    # Test the widget with multiple importers, editors. Specify the viewer and the node class
    base_editor = awb.BasicStructureEditor(title="Basic Editor")
    structure_manager_widget = awb.StructureManagerWidget(
        importers=[
            awb.StructureUploadWidget(title="From computer"),
            awb.StructureBrowserWidget(title="AiiDA database"),
        ],
        editors=[
            base_editor,
            awb.BasicCellEditor(title="Cell Editor"),
        ],
        viewer=awb.viewers.StructureDataViewer(),
        node_class="StructureData",
    )

    assert structure_manager_widget.structure is None
    structure_manager_widget.input_structure = structure_data_object

    # Set action vector perpendicular to screen.
    base_editor.def_perpendicular_to_screen()


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

    # Should not raise for invalid smiles
    widget.smiles.value = "invalid"
    widget._on_button_pressed()
    assert widget.structure is None


@pytest.mark.usefixtures("aiida_profile_clean")
def test_smiles_canonicalization():
    """Test the SMILES canonicalization via RdKit."""
    canonicalize = awb.SmilesWidget.canonicalize_smiles

    # Should not change canonical smiles
    assert canonicalize("C") == "C"

    # Should canonicalize this
    canonical = canonicalize("O=CC=C")
    assert canonical == "C=CC=O"

    # Should be idempotent
    assert canonical == canonicalize(canonical)

    # Should raise for invalid smiles
    with pytest.raises(ValueError):
        canonicalize("invalid")
    # There is another failure mode when RDkit mol object is generated
    # but the canonicalization fails. I do not know how to trigger it though.


@pytest.mark.usefixtures("aiida_profile_clean")
def test_tough_smiles():
    widget = awb.SmilesWidget()
    assert widget.structure is None
    # Regression test for https://github.com/aiidalab/aiidalab-widgets-base/issues/505
    # Throwing in this non-canonical string should not raise
    widget.smiles.value = "C=CC1=C(C2=CC=C(C3=CC=CC=C3)C=C2)C=C(C=C)C(C4=CC=C(C(C=C5)=CC=C5C(C=C6C=C)=C(C=C)C=C6C7=CC=C(C(C=C8)=CC=C8C(C=C9C=C)=C(C=C)C=C9C%10=CC=CC=C%10)C=C7)C=C4)=C1"
    widget._on_button_pressed()
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "C72H54"

    # Regression test for https://github.com/aiidalab/aiidalab-widgets-base/issues/510
    widget.smiles.value = "CC1=C(C)C(C2=C3C=CC4=C(C5=C(C)C(C)=C(C6=C(C=CC=C7)C7=CC8=C6C=CC=C8)C(C)=C5C)C9=CC=C%10N9[Fe]%11(N%12C(C=CC%12=C(C%13=C(C)C(C)=C(C%14=C(C=CC=C%15)C%15=CC%16=C%14C=CC=C%16)C(C)=C%13C)C%17=CC=C2N%17%11)=C%10C%18=C(C)C(C)=C(C%19=C(C=CC=C%20)C%20=CC%21=C%19C=CC=C%21)C(C)=C%18C)N43)=C(C)C(C)=C1C%22=C(C=CC=C%23)C%23=CC%24=C%22C=CC=C%24"
    widget._on_button_pressed()
    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "C116H92FeN4"


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

    # Change the cell parameters.
    widget.cell_parameters.children[2].children[1].value = 10.0
    widget._apply_cell_parameters()
    assert widget.structure.cell.cellpar()[2] == 10.0

    # make supercell using cell transformation
    widget.cell_transformation.children[0].children[0].value = 2
    widget._apply_cell_transformation()
    assert widget.structure.get_chemical_formula() == "Si4"
    # reset the cell transformation matrix
    widget._reset_cell_transformation_matrix()
    assert widget.cell_transformation.children[0].children[0].value == 1


@pytest.mark.usefixtures("aiida_profile_clean")
def test_basic_structure_editor(structure_data_object):
    """Test the `BasicStructureEditor`."""
    widget = awb.BasicStructureEditor()
    assert widget.structure is None

    # Set the structure.
    widget.structure = structure_data_object.get_ase()

    # Set first vector point vector to the first atom.
    widget.selection = [0]
    widget.def_axis_p1()
    assert widget.axis_p1.value == "0.0 0.0 0.0"

    # Set action point to the first atom.
    widget.def_point()
    assert widget.point.value == "0.0 0.0 0.0"

    # Set second vector point vector to the second atom.
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

    # Add a ligand.
    widget.ligand.label = "Methyl -CH3"
    widget.selection = [2]
    widget.add()
    assert len(widget.structure) == 7
    assert widget.structure.get_chemical_formula() == "C2H3OSi"
