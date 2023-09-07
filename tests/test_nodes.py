import pytest

from aiidalab_widgets_base import nodes


@pytest.mark.usefixtures("aiida_profile_clean")
def test_nodes_tree_widget(multiply_add_completed_workchain):
    """Test ProcessNodesTreeWidget with a simple `WorkChainNode`"""

    process = multiply_add_completed_workchain
    tree = nodes.NodesTreeWidget()
    tree.nodes = [process]

    # main node is selected
    assert tree.find_node(process.pk).selected is False

    # test the tree node with pk -999 is not in the tree, and raises KeyError
    with pytest.raises(KeyError):
        tree.find_node(-999)

    # the process has two descendants, they finished successfully
    for descendant_process in process.called_descendants:
        tree_node = tree.find_node(descendant_process.pk)
        assert descendant_process.is_finished_ok
        assert tree_node.icon_style == "success"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_open_aiida_node_in_app_widget(multiply_add_completed_workchain):
    """ "Test OpenAiidaNodeInAppWidget with a simple `WorkChainNode`"""

    process = multiply_add_completed_workchain
    open_node_in_app = nodes.OpenAiidaNodeInAppWidget()

    assert len(open_node_in_app.tab.children) == 0

    open_node_in_app.node = process

    assert len(open_node_in_app.tab.children) > 0
    assert open_node_in_app.tab._titles == {
        "0": "Geometry Optimization",
        "1": "Geometry analysis",
        "2": "Isotherm",
    }
