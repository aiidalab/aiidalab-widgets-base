import pytest
from aiida import orm

from aiidalab_widgets_base import viewers


@pytest.mark.usefixtures("aiida_profile_clean")
def test_pbc_structure_data_viewer(structure_data_object):
    """Test the periodicity of the structure viewer widget."""

    import ase

    from aiidalab_widgets_base import viewers

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
def test_several_data_viewers(
    bands_data_object, folder_data_object, generate_calc_job_node
):
    v = viewers.viewer(orm.Int(1))

    # No viewer for Int, so it should return the input
    assert isinstance(v, orm.Int)

    # DictViewer
    v = viewers.viewer(orm.Dict(dict={"a": 1}))
    assert isinstance(v, viewers.DictViewer)

    # BandsDataViewer
    v = viewers.viewer(bands_data_object)
    assert isinstance(v, viewers.BandsDataViewer)

    # FolderDataViewer
    v = viewers.viewer(folder_data_object)
    assert isinstance(v, viewers.FolderDataViewer)

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
def test_structure_data_viwer(structure_data_object):
    v = viewers.viewer(structure_data_object)
    assert isinstance(v, viewers.StructureDataViewer)

    # Check the `_prepare_payload` function used for downloading.
    format_cases = [
        (
            "Extended xyz",
            """MgpMYXR0aWNlPSIzLjg0NzM3IDAuMCAwLjAgMS45MjM2ODUgMy4zMzE5MiAwLjAgMS45MjM2ODUgMS4xMTA2NCAzLjE0MTM2NCIgUHJvcGVydGllcz1zcGVjaWVzOlM6MTpwb3M6UjozOm1hc3NlczpSOjE6X2FpaWRhbGFiX3ZpZXdlcl9yZXByZXNlbnRhdGlvbl9kZWZhdWx0OlI6MSBwYmM9IlQgVCBUIgpTaSAgICAgICAwLjAwMDAwMDAwICAgICAgIDAuMDAwMDAwMDAgICAgICAgMC4wMDAwMDAwMCAgICAgIDI4LjA4NTUwMDAwICAgICAgIDAuMDAwMDAwMDAKU2kgICAgICAgMS45MjM2ODUwMCAgICAgICAxLjExMDY0MDAwICAgICAgIDAuNzg1MzQxMDAgICAgICAyOC4wODU1MDAwMCAgICAgICAwLjAwMDAwMDAwCg==""",
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

    # Selection of atoms.

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
