import pytest
from aiida import orm

from aiidalab_widgets_base import viewers


@pytest.mark.usefixtures("aiida_profile_clean")
def test_pbc_structure_data_viewer(structure_data_object):
    """Test the periodicity of the structure viewer widget."""

    import ase

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
def test_structure_data_viewer(structure_data_object):
    v = viewers.viewer(structure_data_object)
    assert isinstance(v, viewers.StructureDataViewer)

    # Selection of atoms.

    # Direct selection.
    v._selected_atoms.value = "1..2"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]

    # The x coordinate lower than 0.5.
    v._selected_atoms.value = "x<0.5"
    v.apply_displayed_selection()
    assert v.selection == [0]

    # The id of the second atom
    v._selected_atoms.value = "id > 1"
    v.apply_displayed_selection()
    assert v.selection == [1]

    # or of the two selections.
    v._selected_atoms.value = "x>0.5 or x<0.5"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]

    # Check the `_prepare_payload` function used for downloading.
    format_cases = [
        (
            "Extended xyz",
            """MgpMYXR0aWNlPSIzLjg0NzM3IDAuMCAwLjAgMS45MjM2ODUgMy4zMzE5MiAwLjAgMS45MjM2ODUgMS4xMTA2NCAzLjE0MTM2NCIgUHJvcGVydGllcz1zcGVjaWVzOlM6MTpwb3M6UjozOm1hc3NlczpSOjEgcGJjPSJUIFQgVCIKU2kgICAgICAgMC4wMDAwMDAwMCAgICAgICAwLjAwMDAwMDAwICAgICAgIDAuMDAwMDAwMDAgICAgICAyOC4wODU1MDAwMApTaSAgICAgICAxLjkyMzY4NTAwICAgICAgIDEuMTEwNjQwMDAgICAgICAgMC43ODUzNDEwMCAgICAgIDI4LjA4NTUwMDAwCg==""",
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
