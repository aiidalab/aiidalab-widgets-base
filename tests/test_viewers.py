import pytest
from aiida import orm


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
    from aiidalab_widgets_base import viewer, viewers

    v = viewer(orm.Int(1))

    # No viewer for Int, so it should return the input
    assert isinstance(v, orm.Int)

    # DictViewer
    v = viewer(orm.Dict(dict={"a": 1}))
    assert isinstance(v, viewers.DictViewer)

    # BandsDataViewer
    v = viewer(bands_data_object)
    assert isinstance(v, viewers.BandsDataViewer)

    # FolderDataViewer
    v = viewer(folder_data_object)
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
    v = viewer(process)
    assert isinstance(v, viewers.ProcessNodeViewerWidget)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_structure_data_viwer(structure_data_object):
    from aiidalab_widgets_base import viewer, viewers

    v = viewer(structure_data_object)
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
    output = v._prepare_payload()
    assert (
        output
        == """MgpMYXR0aWNlPSIzLjg0NzM3IDAuMCAwLjAgMS45MjM2ODUgMy4zMzE5MiAwLjAgMS45MjM2ODUgMS4xMTA2NCAzLjE0MTM2NCIgUHJvcGVydGllcz1zcGVjaWVzOlM6MTpwb3M6UjozOm1hc3NlczpSOjEgcGJjPSJUIFQgVCIKU2kgICAgICAgMC4wMDAwMDAwMCAgICAgICAwLjAwMDAwMDAwICAgICAgIDAuMDAwMDAwMDAgICAgICAyOC4wODU1MDAwMApTaSAgICAgICAxLjkyMzY4NTAwICAgICAgIDEuMTEwNjQwMDAgICAgICAgMC43ODUzNDEwMCAgICAgIDI4LjA4NTUwMDAwCg=="""
    )
