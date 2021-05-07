"""Widgets to work with AiiDA nodes."""
import traitlets
import ipywidgets as ipw
from IPython.display import clear_output
from IPython.display import display
from aiida.cmdline.utils.ascii_vis import calc_info
from aiida.engine import ProcessState
from aiida.orm import CalcFunctionNode
from aiida.orm import CalcJobNode
from aiida.orm import Node
from aiida.orm import ProcessNode
from aiida.orm import WorkChainNode
from aiida.orm import load_node
from ipytree import Node as TreeNode
from ipytree import Tree


class AiidaNodeTreeNode(TreeNode):
    def __init__(self, pk, name, **kwargs):
        self.pk = pk
        self.nodes_registry = dict()
        super().__init__(name=name, **kwargs)

    @traitlets.default("opened")
    def _default_openend(self):
        return False


class AiidaProcessNodeTreeNode(AiidaNodeTreeNode):
    def __init__(self, pk, **kwargs):
        self.outputs_node = AiidaOutputsTreeNode(name="outputs", parent_pk=pk)
        super().__init__(pk=pk, **kwargs)


class WorkChainProcessTreeNode(AiidaProcessNodeTreeNode):
    icon = traitlets.Unicode("chain").tag(sync=True)


class CalcJobTreeNode(AiidaProcessNodeTreeNode):
    icon = traitlets.Unicode("gears").tag(sync=True)


class CalcFunctionTreeNode(AiidaProcessNodeTreeNode):
    icon = traitlets.Unicode("gear").tag(sync=True)


class AiidaOutputsTreeNode(TreeNode):
    icon = traitlets.Unicode("folder").tag(sync=True)
    disabled = traitlets.Bool(True).tag(sync=True)

    def __init__(self, name, parent_pk, **kwargs):
        self.parent_pk = parent_pk
        self.nodes_registry = dict()
        super().__init__(name=name, **kwargs)


class UnknownTypeTreeNode(AiidaNodeTreeNode):
    icon = traitlets.Unicode("file").tag(sync=True)


class NodesTreeWidget(ipw.Output):
    """A tree widget for the structured representation of a nodes graph."""

    nodes = traitlets.Tuple().tag(trait=traitlets.Instance(Node))
    selected_nodes = traitlets.Tuple(read_only=True).tag(trait=traitlets.Instance(Node))

    PROCESS_STATE_STYLE = {
        ProcessState.EXCEPTED: "danger",
        ProcessState.FINISHED: "success",
        ProcessState.KILLED: "warning",
        ProcessState.RUNNING: "info",
        ProcessState.WAITING: "info",
    }

    PROCESS_STATE_STYLE_DEFAULT = "default"

    NODE_TYPE = {
        WorkChainNode: WorkChainProcessTreeNode,
        CalcFunctionNode: CalcFunctionTreeNode,
        CalcJobNode: CalcJobTreeNode,
    }

    def __init__(self, **kwargs):
        self._tree = Tree()
        self._tree.observe(self._observe_tree_selected_nodes, ["selected_nodes"])

        super().__init__(**kwargs)

    def _refresh_output(self):
        # There appears to be a bug in the ipytree implementation that sometimes
        # causes the output to not be properly cleared. We therefore refresh the
        # displayed tree upon change of the process trait.
        with self:
            clear_output()
            display(self._tree)

    def _observe_tree_selected_nodes(self, change):
        return self.set_trait(
            "selected_nodes",
            tuple(
                load_node(pk=node.pk) for node in change["new"] if hasattr(node, "pk")
            ),
        )

    def _convert_to_tree_nodes(self, old_nodes, new_nodes):
        "Convert nodes into tree nodes while re-using already converted nodes."
        old_nodes_ = {node.pk: node for node in old_nodes}
        assert len(old_nodes_) == len(old_nodes)  # no duplicated nodes

        for node in new_nodes:
            if node.pk in old_nodes_:
                yield old_nodes_[node.pk]
            else:
                yield self._to_tree_node(node, opened=True)

    @traitlets.observe("nodes")
    def _observe_nodes(self, change):
        self._tree.nodes = list(
            sorted(
                self._convert_to_tree_nodes(
                    old_nodes=self._tree.nodes, new_nodes=change["new"]
                ),
                key=lambda node: node.pk,
            )
        )
        self.update()
        self._refresh_output()

    @classmethod
    def _to_tree_node(cls, node, name=None, **kwargs):
        """Convert an AiiDA node to a tree node."""
        if name is None:
            if isinstance(node, ProcessNode):
                name = calc_info(node)
            else:
                name = str(node)
        return cls.NODE_TYPE.get(type(node), UnknownTypeTreeNode)(
            pk=node.pk, name=name, **kwargs
        )

    @classmethod
    def _find_called(cls, root):
        assert isinstance(root, AiidaProcessNodeTreeNode)
        process_node = load_node(root.pk)
        called = process_node.called
        called.sort(key=lambda p: p.ctime)
        for node in called:
            if node.pk not in root.nodes_registry:
                try:
                    name = calc_info(node)
                except AttributeError:
                    name = str(node)

                root.nodes_registry[node.pk] = cls._to_tree_node(node, name=name)
            yield root.nodes_registry[node.pk]

    @classmethod
    def _find_outputs(cls, root):
        assert isinstance(root, AiidaOutputsTreeNode)
        process_node = load_node(root.parent_pk)
        outputs = {k: process_node.outputs[k] for k in process_node.outputs}
        for key in sorted(outputs.keys(), key=lambda k: outputs[k].pk):
            output_node = outputs[key]
            if output_node.pk not in root.nodes_registry:
                root.nodes_registry[output_node.pk] = cls._to_tree_node(
                    output_node, name=f"{key}<{output_node.pk}>"
                )
            yield root.nodes_registry[output_node.pk]

    @classmethod
    def _find_children(cls, root):
        """Find all children of the provided AiiDA node."""
        if isinstance(root, AiidaProcessNodeTreeNode):
            yield root.outputs_node
            yield from cls._find_called(root)
        elif isinstance(root, AiidaOutputsTreeNode):
            yield from cls._find_outputs(root)

    @classmethod
    def _build_tree(cls, root):
        """Recursively build a tree nodes graph for a given tree node."""
        root.nodes = [cls._build_tree(child) for child in cls._find_children(root)]
        return root

    @classmethod
    def _walk_tree(cls, root):
        """Breadth-first search of the node tree."""
        yield root
        for node in root.nodes:
            yield from cls._walk_tree(node)

    def _update_tree_node(self, tree_node):
        if isinstance(tree_node, AiidaProcessNodeTreeNode):
            process_node = load_node(tree_node.pk)
            tree_node.name = calc_info(process_node)
            tree_node.icon_style = self.PROCESS_STATE_STYLE.get(
                process_node.process_state, self.PROCESS_STATE_STYLE_DEFAULT
            )

    def update(self, _=None):
        """Refresh nodes based on the latest state of the root process and its children."""
        for root_node in self._tree.nodes:
            self._build_tree(root_node)
            for tree_node in self._walk_tree(root_node):
                self._update_tree_node(tree_node)

    def find_node(self, pk):
        for node in self._walk_tree(self._tree):
            if getattr(node, "pk", None) == pk:
                return node
        raise KeyError(pk)
