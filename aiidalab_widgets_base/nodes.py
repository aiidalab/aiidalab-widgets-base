"""Widgets to work with AiiDA nodes."""
import ipywidgets as ipw
import traitlets
from aiida.cmdline.utils.ascii_vis import calc_info
from aiida.engine import ProcessState
from aiida.orm import (
    CalcFunctionNode,
    CalcJobNode,
    Node,
    ProcessNode,
    WorkChainNode,
    load_node,
)
from aiidalab.app import _AiidaLabApp
from IPython.display import clear_output, display
from ipytree import Node as TreeNode
from ipytree import Tree

CALCULATION_TYPES = [
    (
        "geo_opt",
        "Geometry Optimization",
        "Geometry Optimization - typically this is the first step needed to find optimal positions of atoms in the unit cell.",
    ),
    (
        "geo_analysis",
        "Geometry analysis",
        "Geometry analysis - calculate parameters describing the geometry of a material.",
    ),
    (
        "isotherm",
        "Isotherm",
        "Isotherm - compute adsorption isotherm of a small molecules in the selected material.",
    ),
]

SELECTED_APPS = [
    {
        "name": "quantum-espresso",
        "calculation_type": "geo_opt",
        "notebook": "qe.ipynb",
        "parameter_name": "structure_uuid",
        "description": "Optimize atomic positions and/or unit cell employing Quantum ESPRESSO. Quantum ESPRESSO is preferable for small structures with no cell dimensions larger than 15 Å. Additionally, you can choose to compute electronic properties of the material such as band structure and density of states.",
    },
    {
        "name": "aiidalab-lsmo",
        "calculation_type": "geo_opt",
        "notebook": "multistage_geo_opt_ddec.ipynb",
        "parameter_name": "structure_uuid",
        "description": "Optimize atomic positions and unit cell with CP2K. CP2K is very efficient for large (any cell dimension is larger than 15 Å) and/or porous structures. Additionally, you can choose to assign point charges to the atoms using DDEC.",
    },
    {
        "name": "aiidalab-lsmo",
        "calculation_type": "geo_analysis",
        "notebook": "pore_analysis.ipynb",
        "parameter_name": "structure_uuid",
        "description": "Calculate descriptors for the pore geometry using the Zeo++.",
    },
    {
        "name": "aiidalab-lsmo",
        "calculation_type": "isotherm",
        "notebook": "compute_isotherm.ipynb",
        "parameter_name": "structure_uuid",
        "description": "Compute adsorption isotherm of the selected material using the RASPA code. Typically, one needs to optimize geometry and compute the charges of material before computing the isotherm. However, if this is already done, you can go for it.",
    },
]


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


class _AppIcon:
    def __init__(self, app, path_to_root, node):

        name = app["name"]
        app_object = _AiidaLabApp.from_id(name)
        self.logo = app_object.logo
        if app_object.is_installed():
            self.link = f"{path_to_root}{app['name']}/{app['notebook']}?{app['parameter_name']}={node.uuid}"
        else:
            self.link = f"{path_to_root}home/single_app.ipynb?app={app['name']}"
        self.description = app["description"]

    def to_html_string(self):
        return f"""
            <table style="border-collapse:separate;border-spacing:15px;">
            <tr>
                <td style="width:200px"> <a href="{self.link}" target="_blank">  <img src="{self.logo}"> </a></td>
                <td style="width:800px"> <p style="font-size:16px;">{self.description} </p></td>
            </tr>
            </table>
            """


class OpenAiidaNodeInAppWidget(ipw.VBox):

    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):
        self.path_to_root = path_to_root
        self.tab = ipw.Tab(style={"description_width": "initial"})
        self.tab_selection = ipw.RadioButtons(
            options=[],
            description="",
            disabled=False,
            style={"description_width": "initial"},
            layout=ipw.Layout(width="auto"),
        )
        spacer = ipw.HTML("""<p style="margin-bottom:1cm;"></p>""")
        super().__init__(children=[self.tab_selection, spacer, self.tab], **kwargs)

    @traitlets.observe("node")
    def _observe_node(self, change):
        if change["new"]:
            self.tab.children = [
                self.get_tab_content(apps_type=calctype[0])
                for calctype in CALCULATION_TYPES
            ]
            for i, calctype in enumerate(CALCULATION_TYPES):
                self.tab.set_title(i, calctype[1])

            self.tab_selection.options = [
                (calctype[1], i) for i, calctype in enumerate(CALCULATION_TYPES)
            ]

            ipw.link((self.tab, "selected_index"), (self.tab_selection, "value"))
        else:
            self.tab.children = []

    def get_tab_content(self, apps_type):

        tab_content = ipw.HTML("")

        for app in SELECTED_APPS:
            if app["calculation_type"] != apps_type:
                continue
            tab_content.value += _AppIcon(
                app=app,
                path_to_root=self.path_to_root,
                node=self.node,
            ).to_html_string()

        return tab_content
