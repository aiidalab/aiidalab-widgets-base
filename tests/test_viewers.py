import ase
import pytest
import traitlets as tl
from aiida import orm

from aiidalab_widgets_base import viewers


@pytest.mark.usefixtures("aiida_profile_clean")
def test_pbc_structure_data_viewer(structure_data_object):
    """Test the periodicity of the structure viewer widget."""
    # Prepare a structure with periodicity xy
    ase_input = ase.Atoms(
        symbols="Li2",
        positions=[(0.0, 0.0, 0.0), (1.5, 1.5, 1.5)],
        pbc=[True, True, False],
        cell=[3.5, 3.5, 3.5],
    )
    viewer = viewers.StructureDataViewer()
    viewer.structure = ase_input
    assert viewer.periodicity.value == "Periodicity: xy"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_several_data_viewers(bands_data_object, generate_calc_job_node):
    v = viewers.viewer(orm.Int(1))

    # No viewer for Int, so it should return the input
    assert isinstance(v, orm.Int)

    # DictViewer
    v = viewers.viewer(orm.Dict(dict={"a": 1}))
    assert isinstance(v, viewers.DictViewer)

    # BandsDataViewer
    v = viewers.viewer(bands_data_object)
    assert isinstance(v, viewers.BandsDataViewer)

    # ProcessNodeViewer
    process = generate_calc_job_node(
        inputs={
            "parameters": orm.Int(1),
            "nested": {
                "inner": orm.Int(2),
            },
        }
    )
    v = viewers.viewer(process)
    assert isinstance(v, viewers.ProcessNodeViewerWidget)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_folder_data_viewer(folder_data_object):
    v = viewers.viewer(folder_data_object)
    assert isinstance(v, viewers.FolderDataViewer)

    v.files.value = "test1.txt"
    assert v.text.value == "content of test1.txt"

    v.files.value = "test2.txt"
    assert v.text.value == "content of test2.txt"
    v.download_btn.click()
    # NOTE: We're testing the download() method directly as well,
    # since triggering it via self.download_btn.click() callback
    # seems to swallow all exceptions.
    v.download()

    v.files.value = "test.bin"
    assert v.text.value == "[Binary file, preview not available]"
    v.download()


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_data_viewer_storage(structure_data_object):
    v = viewers.viewer(structure_data_object)
    assert isinstance(v, viewers.StructureDataViewer)

    # Check the `_prepare_payload` function used for downloading.
    format_cases = [
        (
            "Extended xyz",
            """MgpMYXR0aWNlPSIzLjg0NzM3IDAuMCAwLjAgMS45MjM2ODUgMy4zMzE5MiAwLjAgMS45MjM2ODUgMS4xMTA2NCAzLjE0MTM2NCIgUHJvcGVydGllcz1zcGVjaWVzOlM6MTpwb3M6UjozOm1hc3NlczpSOjE6X2FpaWRhbGFiX3ZpZXdlcl9yZXByZXNlbnRhdGlvbl9kZWZhdWx0Okk6MSBwYmM9IlQgVCBUIgpTaSAgICAgICAwLjAwMDAwMDAwICAgICAgIDAuMDAwMDAwMDAgICAgICAgMC4wMDAwMDAwMCAgICAgIDI4LjA4NTUwMDAwICAgICAgICAwClNpICAgICAgIDEuOTIzNjg1MDAgICAgICAgMS4xMTA2NDAwMCAgICAgICAwLjc4NTM0MTAwICAgICAgMjguMDg1NTAwMDAgICAgICAgIDAK""",
        ),
        (
            "xsf",
            """Q1JZU1RBTApQUklNVkVDCiAzLjg0NzM3MDAwMDAwMDAwIDAuMDAwMDAwMDAwMDAwMDAgMC4wMDAwMDAwMDAwMDAwMAogMS45MjM2ODUwMDAwMDAwMCAzLjMzMTkyMDAwMDAwMDAwIDAuMDAwMDAwMDAwMDAwMDAKIDEuOTIzNjg1MDAwMDAwMDAgMS4xMTA2NDAwMDAwMDAwMCAzLjE0MTM2NDAwMDAwMDAwClBSSU1DT09SRAogMiAxCiAxNCAgICAgMC4wMDAwMDAwMDAwMDAwMCAgICAgMC4wMDAwMDAwMDAwMDAwMCAgICAgMC4wMDAwMDAwMDAwMDAwMAogMTQgICAgIDEuOTIzNjg1MDAwMDAwMDAgICAgIDEuMTEwNjQwMDAwMDAwMDAgICAgIDAuNzg1MzQxMDAwMDAwMDAK""",
        ),
        (
            "cif",
            """ZGF0YV9pbWFnZTAKX2NoZW1pY2FsX2Zvcm11bGFfc3RydWN0dXJhbCAgICAgICBTaTIKX2NoZW1pY2FsX2Zvcm11bGFfc3VtICAgICAgICAgICAgICAiU2kyIgpfY2VsbF9sZW5ndGhfYSAgICAgICAzLjg0NzM3Cl9jZWxsX2xlbmd0aF9iICAgICAgIDMuODQ3MzcKX2NlbGxfbGVuZ3RoX2MgICAgICAgMy44NDczNwpfY2VsbF9hbmdsZV9hbHBoYSAgICA2MApfY2VsbF9hbmdsZV9iZXRhICAgICA2MApfY2VsbF9hbmdsZV9nYW1tYSAgICA2MAoKX3NwYWNlX2dyb3VwX25hbWVfSC1NX2FsdCAgICAiUCAxIgpfc3BhY2VfZ3JvdXBfSVRfbnVtYmVyICAgICAgIDEKCmxvb3BfCiAgX3NwYWNlX2dyb3VwX3N5bW9wX29wZXJhdGlvbl94eXoKICAneCwgeSwgeicKCmxvb3BfCiAgX2F0b21fc2l0ZV90eXBlX3N5bWJvbAogIF9hdG9tX3NpdGVfbGFiZWwKICBfYXRvbV9zaXRlX3N5bW1ldHJ5X211bHRpcGxpY2l0eQogIF9hdG9tX3NpdGVfZnJhY3RfeAogIF9hdG9tX3NpdGVfZnJhY3RfeQogIF9hdG9tX3NpdGVfZnJhY3RfegogIF9hdG9tX3NpdGVfb2NjdXBhbmN5CiAgU2kgIFNpMSAgICAgICAxLjAgIDAuMDAwMDAgIDAuMDAwMDAgIDAuMDAwMDAgIDEuMDAwMAogIFNpICBTaTIgICAgICAgMS4wICAwLjI1MDAwICAwLjI1MDAwICAwLjI1MDAwICAxLjAwMDAK""",
        ),
    ]

    for fmt, out in format_cases:
        v.file_format.label = fmt
        assert v._prepare_payload() == out

    # Monkey patch the viewer to avoid the need for a running X server.
    # fmt: off
    v._viewer._camera_orientation = [
        16.619212980943573, 0, 0, 0,
        0, 16.619212980943573, 0, 0,
        0, 0, 16.619212980943573, 0,
        -1.6859999895095825, -1.6859999895095825, -0.6669999957084656, 1,
    ]
    # fmt: on
    v._render_structure()


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_data_viewer_selection(structure_data_object):
    v = viewers.viewer(structure_data_object)

    # Direct selection.
    v._selected_atoms.value = "1..2"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [0, 1]
    assert "Distance" in v.selection_info.value
    assert "2 atoms selected" in v.selection_info.value

    # The x coordinate lower than 0.5.
    v._selected_atoms.value = "x<0.5"
    v.apply_displayed_selection()
    assert v.selection == [0]
    assert v.displayed_selection == [0]
    assert "1 atoms selected" in v.selection_info.value

    # The id of the second atom
    v._selected_atoms.value = "id > 1"
    v.apply_displayed_selection()
    assert v.selection == [1]

    # or of the two selections.
    v._selected_atoms.value = "x>=0.5 or x<0.5"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]

    # Display 2*2*2 supercell
    v.supercell = [2, 2, 2]
    assert len(v.structure) == 2
    assert len(v.displayed_structure) == 16

    # Test intersection of the selection with the supercell.
    v._selected_atoms.value = "z>0 and z<2.5"
    v.apply_displayed_selection()
    assert v.selection == [1]
    assert v.displayed_selection == [1, 5, 9, 13]

    v._selected_atoms.value = "x<=2.0 and z<3"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [4, 0, 1]
    assert "Angle" in v.selection_info.value
    assert "3 atoms selected" in v.selection_info.value

    # Convert to boron nitride.
    new_structure = v.structure.copy()
    new_structure.symbols = ["B", "N"]
    v.structure = None
    v.structure = new_structure

    # Use "name" and "not" operators.
    v._selected_atoms.value = "z<2 and name B"
    v.apply_displayed_selection()
    assert v.selection == [0]
    assert v.displayed_selection == [0, 4, 8, 12]

    v._selected_atoms.value = "z<2 and name not B"
    v.apply_displayed_selection()
    assert v.selection == [1]
    assert v.displayed_selection == [1, 5, 9, 13]

    v._selected_atoms.value = "z<2 and name not [B, O]"
    v.apply_displayed_selection()
    assert v.selection == [1]
    assert v.displayed_selection == [1, 5, 9, 13]

    # Use "id" operator.
    v._selected_atoms.value = "id == 1 or id == 8"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [0, 7]

    # Use the d_from operator.
    v._selected_atoms.value = "d_from[0,0,0] < 4"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [4, 8, 0, 1, 2]

    # Use the != operator.
    v._selected_atoms.value = "id != 5"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    # Use ^ and - operators.
    v._selected_atoms.value = "(x-4)^2 + (y-2)^2 < 4"
    v.apply_displayed_selection()
    assert v.selection == [1, 0]
    assert v.displayed_selection == [3, 9, 10]

    # Division and multiplication.
    v._selected_atoms.value = "x/2 < 1"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [4, 0, 1, 2]

    v._selected_atoms.value = "x*1.5 < y + z"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
    assert v.displayed_selection == [2, 3, 4, 6, 7]

    # Test wrong syntax.
    assert v.wrong_syntax.layout.visibility == "hidden"
    v._selected_atoms.value = "x--x"
    v.apply_displayed_selection()
    assert v.wrong_syntax.layout.visibility == "visible"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_data_viewer_representation(structure_data_object):
    v = viewers.viewer(structure_data_object)

    # By default, there should be one "default" representation.
    assert len(v._all_representations) == 1
    assert (
        v._all_representations[0].style_id == "_aiidalab_viewer_representation_default"
    )
    assert v._all_representations[0].selection.value == "1..2"

    # Display only one atom.
    v._all_representations[0].selection.value = "1"
    v._apply_representations()
    assert "2" in v.atoms_not_represented.value

    # Add a new representation.
    v._add_representation()
    assert "2" in v.atoms_not_represented.value
    v._all_representations[1].selection.value = "2"
    v._all_representations[0].type.value = "ball+stick"
    v._all_representations[1].type.value = "spacefill"
    v._apply_representations()
    assert v.atoms_not_represented.value == ""

    # Add an atom to the structure.
    new_structure = v.structure.copy()
    new_structure.append(ase.Atom("C", (0.5, 0.5, 0.5)))
    v.structure = None
    v.structure = new_structure

    # The new atom should appear in the default representation.
    assert v._all_representations[0].selection.value == "1 3"
    assert "3" not in v.atoms_not_represented.value

    # Delete the second representation.
    assert v._all_representations[0].delete_button.layout.visibility == "hidden"
    assert v._all_representations[1].delete_button.layout.visibility == "visible"
    v._all_representations[1].delete_button.click()
    assert len(v._all_representations) == 1
    assert "2" in v.atoms_not_represented.value

    # Try to provide different object type than the viewer accepts.
    with pytest.raises(tl.TraitError):
        v.structure = 2

    with pytest.raises(tl.TraitError):
        v.structure = orm.Int(1)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_compute_bonds_in_structure_data_viewer():
    # Check the function to compute bonds.
    water = ase.Atoms(
        symbols=["O", "H", "H"],
        positions=[
            (0.0, 0.0, 0.119262),
            (0.0, 0.763239, -0.477047),
            (0.0, -0.763239, -0.477047),
        ],
    )
    viewer = viewers.StructureDataViewer()
    bonds = viewer._compute_bonds(water)
    assert len(bonds) == 4


@pytest.mark.usefixtures("aiida_profile_clean")
def test_loading_viewer_using_process_type(generate_calc_job_node):
    """Test loading a viewer widget based on the process type of the process node."""
    from aiidalab_widgets_base import register_viewer_widget

    # Define and register a viewer widget for the calculation type identified by "aiida.calculations:abc".
    @register_viewer_widget("aiida.calculations:abc")
    class AbcViewer:
        def __init__(self, node=None):
            self.node = node

    # Generate a calc job node with the specific entry point "abc".
    process = generate_calc_job_node(entry_point_name="abc")
    # Load the viewer widget for the generated process node.
    viewer = viewers.viewer(process)
    # Verify that the loaded viewer is the correct type and is associated with the intended node.
    assert isinstance(
        viewer, AbcViewer
    ), "Viewer is not an instance of the expected viewer class."
    assert viewer.node == process, "Viewer's node does not match the test process node."
