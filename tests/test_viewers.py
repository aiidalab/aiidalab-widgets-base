import pytest
from aiida import orm

from aiidalab_widgets_base import viewers


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

    # Selection of atoms.

    # Direct selection
    v._selected_atoms.value = "1..2"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]

    # x coordinate lower than 0.5
    v._selected_atoms.value = "x<0.5"
    v.apply_displayed_selection()
    assert v.selection == [0]

    # id of the second atom
    v._selected_atoms.value = "id > 1"
    v.apply_displayed_selection()
    assert v.selection == [1]

    # or of the two selections
    v._selected_atoms.value = "x>0.5 or x<0.5"
    v.apply_displayed_selection()
    assert v.selection == [0, 1]
