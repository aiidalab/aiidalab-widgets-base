import ase
import numpy as np
import pytest


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_manager_widget(structure_data_object):
    """Test the `StructureManagerWidget`."""
    import aiidalab_widgets_base as awb

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

    # Store structure and check that it is stored.
    structure_manager_widget.store_structure()
    assert structure_manager_widget.structure_node.is_stored
    assert structure_manager_widget.structure_node.pk is not None

    # Simulate the structure modification.
    new_structure = structure_manager_widget.structure.copy()
    new_structure[0].position += [0, 0, 1]

    structure_manager_widget.structure = new_structure
    assert structure_manager_widget.structure_node.pk is None
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
    import aiidalab_widgets_base as awb

    structure_browser_widget = awb.StructureBrowserWidget()
    assert structure_browser_widget.structure is None

    structure_browser_widget.search()

    # There should be no structures in the database, only the default output "Select structure".
    assert len(structure_browser_widget.results.options) == 1

    # Store the structure and check that it is listed in the widget.
    structure_data_object.store()
    structure_browser_widget.search()
    assert len(structure_browser_widget.results.options) == 2

    print(structure_browser_widget.results.options)
