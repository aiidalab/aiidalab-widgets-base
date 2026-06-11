"""Widgets to work with AiiDA nodes."""

import functools

import ipytree
import ipywidgets as ipw
import traitlets as tl
from aiida import common, engine, orm
from aiida.cmdline.utils.ascii_vis import calc_info
from IPython.display import clear_output, display


class AiidaNodeTreeNode(ipytree.Node):
    def __init__(self, pk, name, **kwargs):
        self.pk = pk
        self.nodes_registry = {}
        super().__init__(name=name, **kwargs)

    @tl.default("opened")
    def _default_opened(self):
        return True


class AiidaProcessNodeTreeNode(AiidaNodeTreeNode):
    def __init__(self, pk, **kwargs):
        self.outputs_node = AiidaOutputsTreeNode(name="outputs", parent_pk=pk)
        super().__init__(pk=pk, **kwargs)


class WorkChainProcessTreeNode(AiidaProcessNodeTreeNode):
    icon = tl.Unicode("chain").tag(sync=True)


class CalcJobTreeNode(AiidaProcessNodeTreeNode):
    icon = tl.Unicode("gears").tag(sync=True)


class CalcFunctionTreeNode(AiidaProcessNodeTreeNode):
    icon = tl.Unicode("gear").tag(sync=True)


class AiidaOutputsTreeNode(ipytree.Node):
    icon = tl.Unicode("folder").tag(sync=True)
    disabled = tl.Bool(False).tag(sync=True)

    def __init__(self, name, parent_pk, namespaces: tuple[str, ...] = (), **kwargs):
        self.parent_pk = parent_pk
        self.nodes_registry = {}
        self.namespaces = namespaces
        super().__init__(name=name, **kwargs)


class UnknownTypeTreeNode(AiidaNodeTreeNode):
    icon = tl.Unicode("file").tag(sync=True)


class NodesTreeWidget(ipw.Output):
    """A tree widget for the structured representation of a nodes graph."""

    nodes = tl.Tuple().tag(trait=tl.Instance(orm.Node))
    selected_nodes = tl.Tuple(read_only=True).tag(trait=tl.Instance(orm.Node))

    PROCESS_STATE_STYLE = {
        engine.ProcessState.EXCEPTED: "danger",
        engine.ProcessState.FINISHED: "success",
        engine.ProcessState.KILLED: "warning",
        engine.ProcessState.RUNNING: "info",
        engine.ProcessState.WAITING: "info",
    }

    PROCESS_STATE_STYLE_DEFAULT = "default"

    NODE_TYPE = {
        orm.WorkChainNode: WorkChainProcessTreeNode,
        orm.CalcFunctionNode: CalcFunctionTreeNode,
        orm.CalcJobNode: CalcJobTreeNode,
    }

    def __init__(self, **kwargs):
        self._tree = ipytree.Tree()
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
        for node in change["new"]:
            # find the selected node and build the tree from it, so that users can expand and explore the tree
            node_pk = (
                node.parent_pk
                if isinstance(node, AiidaOutputsTreeNode)
                else getattr(node, "pk", None)
            )

            self._build_tree(self.find_node(node_pk, getattr(node, "namespaces", None)))
        return self.set_trait(
            "selected_nodes",
            tuple(
                orm.load_node(pk=node.pk)
                for node in change["new"]
                if hasattr(node, "pk")
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

    @tl.observe("nodes")
    def _observe_nodes(self, change):
        self._tree.nodes = sorted(
            self._convert_to_tree_nodes(
                old_nodes=self._tree.nodes, new_nodes=change["new"]
            ),
            key=lambda node: node.pk,
        )
        self.update()
        self._refresh_output()

    @classmethod
    def _to_tree_node(cls, node, name=None, **kwargs):
        """Convert an AiiDA node to a tree node."""
        if name is None:
            if isinstance(node, orm.ProcessNode):
                name = calc_info(node)
            else:
                name = str(node)
        tree_node = cls.NODE_TYPE.get(type(node), UnknownTypeTreeNode)(
            pk=node.pk, name=name, **kwargs
        )
        # Set the style based on the process state of the node
        if isinstance(node, orm.ProcessNode):
            process_state = (
                engine.ProcessState.EXCEPTED if node.is_failed else node.process_state
            )
            tree_node.icon_style = cls.PROCESS_STATE_STYLE.get(
                process_state, cls.PROCESS_STATE_STYLE_DEFAULT
            )

        return tree_node

    @classmethod
    def _find_called(cls, root):
        assert isinstance(root, AiidaProcessNodeTreeNode)
        process_node = orm.load_node(root.pk)
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
        """
        A generator for all (including nested) output nodes.

        Generates an AiidaOutputsTreeNode when encountering a namespace,
        keeping track of the full namespace path to make it accessible via the
        root node in form of a breadth-first search.
        """
        process_node = orm.load_node(root.parent_pk)

        # Gather outputs from node and its namespaces:
        outputs = functools.reduce(
            lambda attr_dict, namespace: attr_dict[namespace],
            root.namespaces or [],
            process_node.outputs,
        )

        # Convert aiida.orm.LinkManager or AttributDict (if namespace presented) to dict
        output_nodes = {key: outputs[key] for key in outputs}

        for key in sorted(
            output_nodes.keys(), key=lambda k: getattr(outputs[k], "pk", -1)
        ):
            node = output_nodes[key]
            if isinstance(node, common.AttributeDict):
                # for namespace tree node attach label and continue recursively
                yield AiidaOutputsTreeNode(
                    name=key,
                    parent_pk=root.parent_pk,
                    namespaces=(*root.namespaces, key),  # attach nested namespace name
                )

            else:
                if node.pk not in root.nodes_registry:
                    root.nodes_registry[node.pk] = cls._to_tree_node(
                        node, name=f"{key}<{node.pk}>"
                    )
                yield root.nodes_registry[node.pk]

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
        """Build a tree nodes graph for a given tree node."""
        root.nodes = list(cls._find_children(root))
        return root

    @classmethod
    def _walk_tree(cls, root):
        """Breadth-first search of the node tree."""
        yield root
        for node in root.nodes:
            yield from cls._walk_tree(node)

    def _update_tree_node(self, tree_node):
        if isinstance(tree_node, AiidaProcessNodeTreeNode):
            process_node = orm.load_node(tree_node.pk)
            if process_node.process_state is None:
                return
            tree_node.name = calc_info(process_node)
            # Override the process state in case that the process node has failed:
            # (This could be refactored with structural pattern matching with py>=3.10.)
            process_state = (
                engine.ProcessState.EXCEPTED
                if process_node.is_failed
                else process_node.process_state
            )
            tree_node.icon_style = self.PROCESS_STATE_STYLE.get(
                process_state, self.PROCESS_STATE_STYLE_DEFAULT
            )

    def update(self, _=None):
        """Refresh nodes based on the latest state of the root process and its children."""
        for root_node in self._tree.nodes:
            self._build_tree(root_node)
            for tree_node in self._walk_tree(root_node):
                self._update_tree_node(tree_node)

    def find_node(self, pk, namespaces=None):
        """Find a node by its pk and namespaces.
        If node is an output node, it is identified by the parent pk and namespaces, otherwise by the pk."""
        for node in self._walk_tree(self._tree):
            node_pk = (
                node.parent_pk
                if isinstance(node, AiidaOutputsTreeNode)
                else getattr(node, "pk", None)
            )
            if node_pk == pk and getattr(node, "namespaces", None) == namespaces:
                return node
        raise KeyError(pk)
