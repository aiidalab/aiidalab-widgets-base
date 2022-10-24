"""Jupyter viewers for AiiDA data objects."""
# pylint: disable=no-self-use

import base64
import itertools
import re
import warnings
from copy import deepcopy
from hashlib import new

import ipywidgets as ipw
import nglview
import numpy as np
import spglib
import traitlets
from aiida.cmdline.utils.common import get_workchain_report
from aiida.cmdline.utils.query import formatting
from aiida.orm import Data, Node
from ase import Atoms, neighborlist
from ase.cell import Cell
from IPython.display import clear_output, display
from matplotlib.colors import to_rgb
from numpy.linalg import norm
from traitlets import (
    Bool,
    Dict,
    Instance,
    Int,
    List,
    Unicode,
    Union,
    default,
    link,
    observe,
    validate,
)
from vapory import (
    Background,
    Camera,
    Cylinder,
    Finish,
    LightSource,
    Pigment,
    Scene,
    Sphere,
    Texture,
)

from .dicts import Colors, Radius
from .misc import CopyToClipboardButton, ReversePolishNotation
from .utils import ase2spglib, list_to_string_range, string_range_to_list

AIIDA_VIEWER_MAPPING = dict()
BOX_LAYOUT = ipw.Layout(
    display="flex-wrap", flex_flow="row wrap", justify_content="space-between"
)


def register_viewer_widget(key):
    """Register widget as a viewer for the given key."""

    def registration_decorator(widget):
        AIIDA_VIEWER_MAPPING[key] = widget
        return widget

    return registration_decorator


def viewer(obj, downloadable=True, **kwargs):
    """Display AiiDA data types in Jupyter notebooks.

    :param downloadable: If True, add link/button to download the content of displayed AiiDA object.
    :type downloadable: bool

    Returns the object itself if the viewer wasn't found."""
    if not isinstance(obj, Node):  # only working with AiiDA nodes
        warnings.warn(f"This viewer works only with AiiDA objects, got {type(obj)}")
        return obj

    try:
        _viewer = AIIDA_VIEWER_MAPPING[obj.node_type]
        return _viewer(obj, downloadable=downloadable, **kwargs)
    except (KeyError) as exc:
        if obj.node_type in str(exc):
            warnings.warn(
                "Did not find an appropriate viewer for the {} object. Returning the object "
                "itself.".format(type(obj))
            )
            return obj
        raise exc


class AiidaNodeViewWidget(ipw.VBox):
    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):
        self._output = ipw.Output()
        super().__init__(
            children=[
                self._output,
            ],
            **kwargs,
        )

    @traitlets.observe("node")
    def _observe_node(self, change):
        if change["new"] != change["old"]:
            with self._output:
                clear_output()
                if change["new"]:
                    display(viewer(change["new"]))


@register_viewer_widget("data.dict.Dict.")
class DictViewer(ipw.VBox):

    value = Unicode()
    """Viewer class for Dict object.

    :param parameter: Dict object to be viewed
    :type parameter: Dict
    :param downloadable: If True, add link/button to download the content of the object
    :type downloadable: bool"""

    def __init__(self, parameter, downloadable=True, **kwargs):
        import pandas as pd

        # Here we are defining properties of 'df' class (specified while exporting pandas table into html).
        # Since the exported object is nothing more than HTML table, all 'standard' HTML table settings
        # can be applied to it as well.
        # For more information on how to controle the table appearance please visit:
        # https://css-tricks.com/complete-guide-table-element/
        self.widget = ipw.HTML()
        ipw.dlink((self, "value"), (self.widget, "value"))

        self.value += """
        <style>
            .df { border: none; }
            .df tbody tr:nth-child(odd) { background-color: #e5e7e9; }
            .df tbody tr:nth-child(odd):hover { background-color:   #f5b7b1; }
            .df tbody tr:nth-child(even):hover { background-color:  #f5b7b1; }
            .df tbody td { min-width: 300px; text-align: center; border: none }
            .df th { text-align: center; border: none;  border-bottom: 1px solid black;}
        </style>
        """

        pd.set_option("max_colwidth", 40)
        dataf = pd.DataFrame(
            [(key, value) for key, value in sorted(parameter.get_dict().items())],
            columns=["Key", "Value"],
        )
        self.value += dataf.to_html(
            classes="df", index=False
        )  # specify that exported table belongs to 'df' class
        # this is used to setup table's appearance using CSS
        if downloadable:
            payload = base64.b64encode(dataf.to_csv(index=False).encode()).decode()
            fname = f"{parameter.pk}.csv"
            to_add = """Download table in csv format: <a download="{filename}"
            href="data:text/csv;base64,{payload}" target="_blank">{title}</a>"""
            self.value += to_add.format(filename=fname, payload=payload, title=fname)

        super().__init__([self.widget], **kwargs)


class Representation(ipw.VBox):
    """Representation for StructureData in nglviewer"""

    master_class = None

    def __init__(self, indices="1..2"):
        self.selection = ipw.Text(
            description="atoms:",
            value="",
            layout=ipw.Layout(width="35%", height="30px"),
        )
        self.repr_type = ipw.Dropdown(
            options=["ball+stick", "spacefill"],
            value="ball+stick",
            description="type",
            disabled=False,
            layout=ipw.Layout(width="35%", height="30px"),
        )
        self.size = ipw.FloatText(
            value=3, description="size", layout=ipw.Layout(width="25%", height="30px")
        )
        self.color = ipw.Dropdown(
            options=["element", "red", "green", "blue", "yellow", "orange", "purple"],
            value="element",
            description="color",
            disabled=False,
            layout=ipw.Layout(width="35%", height="30px"),
        )
        self.show = ipw.Checkbox(value=True, description="show", disabled=False)

        # Delete button.
        self.delete_button = ipw.Button(
            description="Delete",
            button_style="danger",
            layout=ipw.Layout(width="15%", height="30px"),
        )
        self.delete_button.on_click(self.delete_myself)

        super().__init__(
            children=[
                ipw.HBox(
                    [
                        self.selection,
                        self.show,
                        self.delete_button,
                    ]
                ),
                ipw.HBox([self.repr_type, self.size, self.color]),
            ]
        )

    def delete_myself(self, _):
        self.master_class.delete_representation(self)


class _StructureDataBaseViewer(ipw.VBox):
    """Base viewer class for AiiDA structure or trajectory objects.

    :param configure_view: If True, add configuration tabs (deprecated)
    :type configure_view: bool
    :param configuration_tabs: List of configuration tabs (default: ["Selection", "Appearance", "Cell", "Download"])
    :type configure_view: list
    :param default_camera: default camera (orthographic|perspective), can be changed in the Appearance tab
    :type default_camera: string

    """

    all_representations = traitlets.List()
    natoms = Int()
    # brand_new_structure = Bool(True)
    selection = List(Int)
    selection_adv = Unicode()
    supercell = List(Int)
    cell = Instance(Cell, allow_none=True)
    DEFAULT_SELECTION_OPACITY = 0.2
    DEFAULT_SELECTION_RADIUS = 6
    DEFAULT_SELECTION_COLOR = "green"

    def __init__(
        self,
        configure_view=True,
        configuration_tabs=None,
        default_camera="orthographic",
        **kwargs,
    ):
        # Defining viewer box.

        # Nglviwer
        self._viewer = nglview.NGLWidget()
        self._viewer.camera = default_camera
        self._viewer.observe(self._on_atom_click, names="picked")
        self._viewer.stage.set_parameters(mouse_preset="pymol")
        # self.first_update_of_viewer = True
        self.natoms = 0
        self.n_all_representations = 0

        view_box = ipw.VBox([self._viewer])

        configuration_tabs_map = {
            "Cell": self._cell_tab(),
            "Selection": self._selection_tab(),
            "Appearance": self._appearance_tab(),
            "Download": self._download_tab(),
        }

        if configure_view is not True:
            warnings.warn(
                "`configure_view` is deprecated, please use `configuration_tabs` instead.",
                DeprecationWarning,
            )
            if not configure_view:
                configuration_tabs.clear()

        # Constructing configuration box
        if configuration_tabs is None:
            configuration_tabs = ["Selection", "Appearance", "Cell", "Download"]

        if len(configuration_tabs) != 0:
            self.selection_tab_idx = configuration_tabs.index("Selection")
            self.configuration_box = ipw.Tab(
                layout=ipw.Layout(flex="1 1 auto", width="auto")
            )
            self.configuration_box.children = [
                configuration_tabs_map[tab_title] for tab_title in configuration_tabs
            ]

            for i, title in enumerate(configuration_tabs):
                self.configuration_box.set_title(i, title)
            children = [ipw.HBox([view_box, self.configuration_box])]
            view_box.layout = {"width": "60%"}
        else:
            children = [view_box]

        if "children" in kwargs:
            children += kwargs.pop("children")

        super().__init__(children, **kwargs)

    def _selection_tab(self):
        """Defining the selection tab."""

        # 1. Selected atoms.
        self._selected_atoms = ipw.Text(
            description="Selected atoms:",
            value="",
            style={"description_width": "initial"},
        )

        # 2. Copy to clipboard
        copy_to_clipboard = CopyToClipboardButton(description="Copy to clipboard")
        link((self._selected_atoms, "value"), (copy_to_clipboard, "value"))

        # 3. Informing about wrong syntax.
        self.wrong_syntax = ipw.HTML(
            value="""<i class="fa fa-times" style="color:red;font-size:2em;" ></i> wrong syntax""",
            layout={"visibility": "hidden"},
        )

        # 4. Button to clear selection.
        clear_selection = ipw.Button(description="Clear selection")
        # clear_selection.on_click(lambda _: self.set_trait('selection', list()))  # lambda cannot contain assignments
        clear_selection.on_click(self.clear_selection)
        # CLEAR self.wrong_syntax.layout.visibility = 'visible'

        # 5. Button to apply selection
        apply_selection = ipw.Button(description="Apply selection")
        apply_selection.on_click(self.apply_selection)

        self.selection_info = ipw.HTML()

        return ipw.VBox(
            [
                ipw.HBox([self._selected_atoms, self.wrong_syntax]),
                ipw.HTML(
                    value="""
                <p style="font-weight:800;">You can either specify ranges:
                    <font style="font-style:italic;font-weight:400;">1 5..8 10</font>
                </p>
                <p style="font-weight:800;">or expressions:
                    <font style="font-style:italic;font-weight:400;">(x>1 and name not [N,O]) or d_from [1,1,1]>2 or id>=10</font>
                </p>"""
                ),
                ipw.HBox([copy_to_clipboard, clear_selection, apply_selection]),
                self.selection_info,
            ]
        )

    def _appearance_tab(self):
        """Defining the appearance tab."""

        # 1. Supercell
        def change_supercell(_=None):
            self.supercell = [
                _supercell[0].value,
                _supercell[1].value,
                _supercell[2].value,
            ]

        _supercell = [
            ipw.BoundedIntText(value=1, min=1, layout={"width": "30px"}),
            ipw.BoundedIntText(value=1, min=1, layout={"width": "30px"}),
            ipw.BoundedIntText(value=1, min=1, layout={"width": "30px"}),
        ]
        for elem in _supercell:
            elem.observe(change_supercell, names="value")
        supercell_selector = ipw.HBox(
            [ipw.HTML(description="Super cell:")] + _supercell
        )

        # 2. Choose background color.
        background_color = ipw.ColorPicker(description="Background")
        link((background_color, "value"), (self._viewer, "background"))
        background_color.value = "white"

        # 3. Camera switcher
        camera_type = ipw.ToggleButtons(
            options={"Orthographic": "orthographic", "Perspective": "perspective"},
            description="Camera type:",
            value=self._viewer.camera,
            layout={"align_self": "flex-start"},
            style={"button_width": "115.5px"},
            orientation="vertical",
        )

        def change_camera(change):
            self._viewer.camera = change["new"]

        camera_type.observe(change_camera, names="value")

        # 4. Center button.
        center_button = ipw.Button(description="Center molecule")
        center_button.on_click(lambda c: self._viewer.center())

        # 5. representations buttons
        self.atoms_not_represented = ipw.Output()
        self.add_new_rep_button = ipw.Button(description="Add rep", button_style="info")
        self.add_new_rep_button.on_click(self.add_representation)

        apply_rep = ipw.Button(description="Apply rep")
        apply_rep.on_click(self.apply_representations)
        self.representation_output = ipw.Box(layout=BOX_LAYOUT)

        return ipw.VBox(
            [
                supercell_selector,
                background_color,
                camera_type,
                self.add_new_rep_button,
                self.representation_output,
                self.atoms_not_represented,
                apply_rep,
                center_button,
            ]
        )

    def add_representation(self, _):
        """Add a representation to the list of representations."""
        self.all_representations = self.all_representations + [Representation()]
        self.n_all_representations += 1

    def delete_representation(self, representation):
        try:
            index = self.all_representations.index(representation)
        except ValueError:
            self.representation_add_message.message = f"""<span style="color:red">Error:</span> Rep. {representation} not found."""
            return

        self.all_representations = (
            self.all_representations[:index] + self.all_representations[index + 1 :]
        )
        del representation
        self.n_all_representations -= 1
        self.apply_representations()

    @observe("all_representations")
    def _observe_representations(self, change):
        """Update the list of representations."""
        if change["new"]:
            self.representation_output.children = change["new"]
            self.all_representations[-1].master_class = self
        else:
            self.all_representation_output.children = []

    def update_representations(self, change=None):
        """Update the representations using the list of representations"""
        number_of_representation_widgets = len(self.all_representations)
        if self.displayed_structure:
            if number_of_representation_widgets == 0:
                self.n_all_representations = 0
                # self.all_representations = [Representation()]
                self.add_representation(None)

            representations = self.structure.arrays["representations"]
            for rep in set(representations):
                if (
                    rep >= 0
                ):  # negative values are used for atoms not represented (different from the case of hidden representations)
                    self.all_representations[
                        int(rep)
                    ].selection.value = list_to_string_range(
                        [int(i) for i in np.where(representations == rep)[0]], shift=1
                    )
            # empty selection field for unused representations
            for rep in range(number_of_representation_widgets):
                if rep not in {int(i) for i in representations}:
                    self.all_representations[rep].selection.value = ""
            self.apply_representations()

    def representation_parameters(self, representation):
        """Return the parameters dictionary of a representation."""
        idsl = string_range_to_list(representation.selection.value, shift=-1)[0]
        idsl_rep = [
            i + rep * self.natoms
            for rep in range(np.prod(self.supercell))
            for i in idsl
            if self.structure.arrays["representationsshow"][i]
        ]
        ids = self.list_to_nglview(idsl_rep)
        params = {
            "type": representation.repr_type.value,
            "params": {
                "sele": ids,
                "opacity": 1,
                "color": representation.color.value,
            },
        }
        if representation.repr_type.value == "ball+stick":
            params["params"]["aspectRatio"] = representation.size.value
        else:
            params["params"]["radiusScale"] = 0.1 * representation.size.value

        return params

    def apply_representations(self, change=None):
        """Apply the representations to the displayed structure."""
        # negative value means an atom is not assigned to a representation
        self._viewer.clear_representations(component=0)

        # initially not atoms are assigned to a representation
        arrayrepresentations = -1 * np.ones(self.natoms)

        # the atom is not shown
        arrayrepresentationsshow = np.zeros(self.natoms)

        for irep, rep in enumerate(self.all_representations):
            selection = string_range_to_list(rep.selection.value, shift=-1)[0]
            for index in selection:
                arrayrepresentations[index] = irep
                if rep.show.value:
                    arrayrepresentationsshow[index] = 1

        self.structure.set_array("representations", arrayrepresentations)
        self.structure.set_array("representationsshow", arrayrepresentationsshow)

        # when supercell bugs will be fixed, decide on how to handle supercell selections
        # self.displayed_structure.set_array("representations", arrayrepresentations)
        # self.displayed_structure.set_array("representationsshow", arrayrepresentationsshow)
        # iterate on number of representations
        self.repr_params = []
        # self.brand_new_structure=False
        current_rep = 0
        for rep in self.all_representations:
            # in representation dictionary indexes start from 0 so we transform '1..4' in '0..3'
            self.repr_params.append(self.representation_parameters(rep))
            current_rep += 1

        missing_atoms = {
            int(i) for i in np.where(self.structure.arrays["representations"] < 0)[0]
        }
        if missing_atoms:
            self.atoms_not_represented.clear_output()
            with self.atoms_not_represented:
                print(
                    "Atoms excluded from representations: ",
                    list_to_string_range(list(missing_atoms), shift=1),
                )
        else:
            self.atoms_not_represented.clear_output()
        self.update_viewer()
        # if self.first_update_of_viewer:
        # self.first_update_of_viewer = self.orient_z_up()
        self.orient_z_up()

    @observe("cell")
    def _observe_cell(self, _=None):
        # only update cell info when it is a 3D structure.
        if self.cell and all(self.structure.pbc):
            self.cell_a.value = "<i><b>a</b></i>: {:.4f} {:.4f} {:.4f}".format(
                *self.cell.array[0]
            )
            self.cell_b.value = "<i><b>b</b></i>: {:.4f} {:.4f} {:.4f}".format(
                *self.cell.array[1]
            )
            self.cell_c.value = "<i><b>c</b></i>: {:.4f} {:.4f} {:.4f}".format(
                *self.cell.array[2]
            )

            self.cell_a_length.value = "|<i><b>a</b></i>|: {:.4f}".format(
                self.cell.lengths()[0]
            )
            self.cell_b_length.value = "|<i><b>b</b></i>|: {:.4f}".format(
                self.cell.lengths()[1]
            )
            self.cell_c_length.value = "|<i><b>c</b></i>|: {:.4f}".format(
                self.cell.lengths()[2]
            )

            self.cell_alpha.value = f"&alpha;: {self.cell.angles()[0]:.4f}"
            self.cell_beta.value = f"&beta;: {self.cell.angles()[1]:.4f}"
            self.cell_gamma.value = f"&gamma;: {self.cell.angles()[2]:.4f}"

            spglib_structure = ase2spglib(self.structure)
            symmetry_dataset = spglib.get_symmetry_dataset(
                spglib_structure, symprec=1e-5, angle_tolerance=1.0
            )

            self.cell_spacegroup.value = f"Spacegroup: {symmetry_dataset['international']} (No.{symmetry_dataset['number']})"
            self.cell_hall.value = f"Hall: {symmetry_dataset['hall']} (No.{symmetry_dataset['hall_number']})"
        else:
            self.cell_a.value = "<i><b>a</b></i>:"
            self.cell_b.value = "<i><b>b</b></i>:"
            self.cell_c.value = "<i><b>c</b></i>:"

            self.cell_a_length.value = "|<i><b>a</b></i>|:"
            self.cell_b_length.value = "|<i><b>b</b></i>|:"
            self.cell_c_length.value = "|<i><b>c</b></i>|:"

            self.cell_alpha.value = "&alpha;:"
            self.cell_beta.value = "&beta;:"
            self.cell_gamma.value = "&gamma;:"

    def _cell_tab(self):
        self.cell_a = ipw.HTML()
        self.cell_b = ipw.HTML()
        self.cell_c = ipw.HTML()

        self.cell_a_length = ipw.HTML()
        self.cell_b_length = ipw.HTML()
        self.cell_c_length = ipw.HTML()

        self.cell_alpha = ipw.HTML()
        self.cell_beta = ipw.HTML()
        self.cell_gamma = ipw.HTML()

        self.cell_spacegroup = ipw.HTML()
        self.cell_hall = ipw.HTML()

        self._observe_cell()

        return ipw.VBox(
            [
                ipw.HTML("Length unit: angstrom (Å)"),
                ipw.HBox(
                    [
                        ipw.VBox(
                            [
                                ipw.HTML("Cell vectors:"),
                                self.cell_a,
                                self.cell_b,
                                self.cell_c,
                            ]
                        ),
                        ipw.VBox(
                            [
                                ipw.HTML("Сell vectors length:"),
                                self.cell_a_length,
                                self.cell_b_length,
                                self.cell_c_length,
                            ],
                            layout={"margin": "0 0 0 50px"},
                        ),
                    ]
                ),
                ipw.HBox(
                    [
                        ipw.VBox(
                            [
                                ipw.HTML("Angles:"),
                                self.cell_alpha,
                                self.cell_beta,
                                self.cell_gamma,
                            ]
                        ),
                        ipw.VBox(
                            [
                                ipw.HTML("Symmetry information:"),
                                self.cell_spacegroup,
                                self.cell_hall,
                            ],
                            layout={"margin": "0 0 0 50px"},
                        ),
                    ]
                ),
            ]
        )

    def _download_tab(self):
        """Defining the download tab."""

        # 1. Choose download file format.
        self.file_format = ipw.Dropdown(
            options=["xyz", "cif"],
            layout={"width": "200px"},
            description="File format:",
        )

        # 2. Download button.
        self.download_btn = ipw.Button(description="Download")
        self.download_btn.on_click(self.download)
        self.download_box = ipw.VBox(
            children=[
                ipw.Label("Download as file:"),
                ipw.HBox([self.file_format, self.download_btn]),
            ]
        )

        # 3. Screenshot button
        self.screenshot_btn = ipw.Button(description="Screenshot", icon="camera")
        self.screenshot_btn.on_click(lambda _: self._viewer.download_image())
        self.screenshot_box = ipw.VBox(
            children=[ipw.Label("Create a screenshot:"), self.screenshot_btn]
        )

        # 4. Render a high quality image
        self.render_btn = ipw.Button(description="Render", icon="fa-paint-brush")
        self.render_btn.on_click(self._render_structure)
        self.render_box = ipw.VBox(
            children=[ipw.Label("Render an image with POVRAY:"), self.render_btn]
        )

        return ipw.VBox([self.download_box, self.screenshot_box, self.render_box])

    def _render_structure(self, change=None):
        """Render the structure with POVRAY."""

        if not isinstance(self.structure, Atoms):
            return

        self.render_btn.disabled = True
        omat = np.array(self._viewer._camera_orientation).reshape(4, 4).transpose()

        zfactor = norm(omat[0, 0:3])
        omat[0:3, 0:3] = omat[0:3, 0:3] / zfactor

        bb = deepcopy(self.structure.repeat(self.supercell))
        bb.pbc = (False, False, False)

        for i in bb:
            ixyz = omat[0:3, 0:3].dot(np.array([i.x, i.y, i.z]) + omat[0:3, 3])
            i.x, i.y, i.z = -ixyz[0], ixyz[1], ixyz[2]

        vertices = []

        cell = bb.get_cell()
        vertices.append(np.array([0, 0, 0]))
        vertices.extend(cell)
        vertices.extend(
            [
                cell[0] + cell[1],
                cell[0] + cell[2],
                cell[1] + cell[2],
                cell[0] + cell[1] + cell[2],
            ]
        )

        for n, i in enumerate(vertices):
            ixyz = omat[0:3, 0:3].dot(i + omat[0:3, 3])
            vertices[n] = np.array([-ixyz[0], ixyz[1], ixyz[2]])

        bonds = []

        cutOff = neighborlist.natural_cutoffs(
            bb
        )  # Takes the cutoffs from the ASE database
        neighborList = neighborlist.NeighborList(
            cutOff, self_interaction=False, bothways=False
        )
        neighborList.update(bb)
        matrix = neighborList.get_connectivity_matrix()

        for k in matrix.keys():
            i = bb[k[0]]
            j = bb[k[1]]

            v1 = np.array([i.x, i.y, i.z])
            v2 = np.array([j.x, j.y, j.z])
            midi = v1 + (v2 - v1) * Radius[i.symbol] / (
                Radius[i.symbol] + Radius[j.symbol]
            )
            bond = Cylinder(
                v1,
                midi,
                0.2,
                Pigment("color", np.array(Colors[i.symbol])),
                Finish("phong", 0.8, "reflection", 0.05),
            )
            bonds.append(bond)
            bond = Cylinder(
                v2,
                midi,
                0.2,
                Pigment("color", np.array(Colors[j.symbol])),
                Finish("phong", 0.8, "reflection", 0.05),
            )
            bonds.append(bond)

        edges = []
        for x, i in enumerate(vertices):
            for j in vertices[x + 1 :]:
                if (
                    norm(np.cross(i - j, vertices[1] - vertices[0])) < 0.001
                    or norm(np.cross(i - j, vertices[2] - vertices[0])) < 0.001
                    or norm(np.cross(i - j, vertices[3] - vertices[0])) < 0.001
                ):
                    edge = Cylinder(
                        i,
                        j,
                        0.06,
                        Texture(
                            Pigment("color", [212 / 255.0, 175 / 255.0, 55 / 255.0])
                        ),
                        Finish("phong", 0.9, "reflection", 0.01),
                    )
                    edges.append(edge)

        camera = Camera(
            "perspective",
            "location",
            [0, 0, -zfactor / 1.5],
            "look_at",
            [0.0, 0.0, 0.0],
        )
        light = LightSource([0, 0, -100.0], "color", [1.5, 1.5, 1.5])

        spheres = [
            Sphere(
                [i.x, i.y, i.z],
                Radius[i.symbol],
                Texture(Pigment("color", np.array(Colors[i.symbol]))),
                Finish("phong", 0.9, "reflection", 0.05),
            )
            for i in bb
        ]

        objects = (
            [light]
            + spheres
            + edges
            + bonds
            + [Background("color", np.array(to_rgb(self._viewer.background)))]
        )

        scene = Scene(camera, objects=objects)
        fname = bb.get_chemical_formula() + ".png"
        scene.render(
            fname,
            width=2560,
            height=1440,
            antialiasing=0.000,
            quality=11,
            remove_temp=False,
        )
        with open(fname, "rb") as raw:
            payload = base64.b64encode(raw.read()).decode()
        self._download(payload=payload, filename=fname)
        self.render_btn.disabled = False

    def _on_atom_click(self, _=None):
        """Update selection when clicked on atom."""
        if hasattr(self._viewer, "component_0"):
            if "atom1" not in self._viewer.picked.keys():
                return  # did not click on atom
            index = self._viewer.picked["atom1"]["index"]
            # component = self._viewer.picked["component"]

            selection = self.selection.copy()

            if selection:
                if index not in selection:
                    selection.append(index)
                else:
                    selection.remove(index)
            else:
                selection = [index]

            # selection_unit = [i for i in selection if i < self.natoms]
            self.selection = selection
            # self.selection = selection_unit

        return

    def list_to_nglview(self, list):
        """Converts a list of structures to a nglview widget"""
        sele = "none"
        if list:
            sele = "@" + ",".join(str(s) for s in list)
        return sele

    def highlight_atoms(
        self,
        vis_list,
    ):
        """Highlighting atoms according to the provided list."""
        if not hasattr(self._viewer, "component_0"):
            return

        
        # Map vis_list and self.displayed_structure.arrays["representations"] to a list of strings
        # that goes to the highlight_reps
        # there are N representations defined by the user and N automatically added for highlighting
        ids = [[] for rep in range(self.n_all_representations)]

        for i in vis_list:
            ids[int(self.structure.arrays["representations"][i])].append(i)

        # remove previous highlight_rep representations
        for i in range(self.n_all_representations):
            self._viewer._remove_representations_by_name(repr_name="highlight_rep" + str(i), component=0)

        # create the dictionaries for highlight_reps
        for i, selection in enumerate(ids):
            if selection:
                params = self.representation_parameters(self.all_representations[i])
                params["params"]["sele"] = self.list_to_nglview(selection)
                params["params"]["name"] = "highlight_rep" + str(i)
                params["params"]["color"] = "red"
                params["params"]["opacity"] = 0.6
                params["params"]["component_index"] = 0
                if "radiusScale" in params["params"]:
                    params["params"]["radiusScale"] += 0.1
                else:
                    params["params"]["aspectRatio"] += 0.1

                # and use directly teh remote call for more flexibility
                self._viewer._remote_call(
                    "addRepresentation",
                    target="compList",
                    args=[params["type"]],
                    kwargs=params["params"],
                )


    def remove_viewer_components(self, c=None):
        with self.hold_trait_notifications():
            while hasattr(self._viewer, "component_0"):
                self._viewer.component_0.clear_representations()
                cid = self._viewer.component_0.id
                self._viewer.remove_component(cid)

    def update_viewer(self, c=None):

        if self.displayed_structure:
            self._viewer.set_representations(self.repr_params, component=0)
            self._viewer.add_unitcell()
            self._viewer.center()

    def orient_z_up(self, _=None):
        try:
            if self.structure is not None:
                cell_z = self.structure.cell[2, 2]
                com = self.structure.get_center_of_mass()
                def_orientation = self._viewer._camera_orientation
                top_z_orientation = [
                    1.0,
                    0.0,
                    0.0,
                    0,
                    0.0,
                    1.0,
                    0.0,
                    0,
                    0.0,
                    0.0,
                    -np.max([cell_z, 30.0]),
                    0,
                    -com[0],
                    -com[1],
                    -com[2],
                    1,
                ]
                self._viewer._set_camera_orientation(top_z_orientation)
                self._viewer.center()
                return False
            else:
                return True
        except AttributeError:
            return True

    @default("supercell")
    def _default_supercell(self):
        return [1, 1, 1]

    @default("selection")
    def _default_selection(self):
        return list()

    @validate("selection")
    def _validate_selection(self, provided):
        return list(provided["value"])

    @observe("selection")
    def _observe_selection(self, _=None):
        self.highlight_atoms(self.selection)
        self._selected_atoms.value = list_to_string_range(self.selection, shift=1)

        # if atom is selected from nglview, shift to selection tab
        if self._selected_atoms.value:
            self.configuration_box.selected_index = self.selection_tab_idx

    def clear_selection(self, _=None):
        self.set_trait("selection", list()),
        self.set_trait("selection_adv", ""),

    def apply_selection(self, _=None):
        """Apply selection specified in the text field."""
        selection_string = self._selected_atoms.value
        expanded_selection, syntax_ok = string_range_to_list(
            self._selected_atoms.value, shift=-1
        )
        # self.wrong_syntax.layout.visibility = 'hidden' if syntax_ok else 'visible'
        if syntax_ok:
            self.wrong_syntax.layout.visibility = "hidden"
            self.selection = expanded_selection
            self.selection = expanded_selection
            self._selected_atoms.value = (
                selection_string  # Keep the old string for further editing.
            )
        else:
            self.selection_adv = selection_string

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare a structure for downloading."""
        suffix = f"-pk-{self.pk}" if self.pk else ""
        self._download(
            payload=self._prepare_payload(),
            filename=f"structure{suffix}.{self.file_format.value}",
        )

    @staticmethod
    def _download(payload, filename):
        """Download payload as a file named as filename."""
        from IPython.display import Javascript

        javas = Javascript(
            """
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(
                payload=payload, filename=filename
            )
        )
        display(javas)

    def _prepare_payload(self, file_format=None):
        """Prepare binary information."""
        from tempfile import NamedTemporaryFile

        file_format = file_format if file_format else self.file_format.value
        tmp = NamedTemporaryFile()
        self.structure.write(tmp.name, format=file_format)  # pylint: disable=no-member
        with open(tmp.name, "rb") as raw:
            return base64.b64encode(raw.read()).decode()

    @property
    def thumbnail(self):
        return self._prepare_payload(file_format="png")


@register_viewer_widget("data.cif.CifData.")
@register_viewer_widget("data.structure.StructureData.")
class StructureDataViewer(_StructureDataBaseViewer):
    """Viewer class for AiiDA structure objects.

    Attributes:
        structure (Atoms, StructureData, CifData): Trait that contains a structure object,
        which was initially provided to the viewer. It can be either directly set to an
        ASE Atoms object or to AiiDA structure object containing `get_ase()` method.

        displayed_structure (Atoms): Trait that contains a structure object that is
        currently displayed (super cell, for example). The trait is generated automatically
        and can't be set outside of the class.
    """

    structure = Union([Instance(Atoms), Instance(Node)], allow_none=True)
    displayed_structure = Instance(Atoms, allow_none=True, read_only=True)
    pk = Int(allow_none=True)

    def __init__(self, structure=None, **kwargs):
        super().__init__(**kwargs)
        self.structure = structure
        # self.supercell.observe(self.repeat, names='value')

    @observe("supercell")
    def repeat(self, _=None):
        if self.structure is not None:
            self.set_trait("displayed_structure", self.structure.repeat(self.supercell))
            self.apply_representations()

    @validate("structure")
    def _valid_structure(self, change):  # pylint: disable=no-self-use
        """Update structure."""
        self.remove_viewer_components()
        self.clear_selection()
        structure = change["value"]
        if structure is None:
            return None  # if no structure provided, the rest of the code can be skipped
        if isinstance(structure, Atoms):
            self.pk = None
        elif isinstance(structure, Node):
            self.pk = structure.pk
            structure = structure.get_ase()
        else:
            raise ValueError(
                "Unsupported type {}, structure must be one of the following types: "
                "ASE Atoms object, AiiDA CifData or StructureData."
            )
        self.natoms = len(structure)
        if "representations" not in structure.arrays:
            structure.set_array("representations", np.zeros(self.natoms))
        if "representationsshow" not in structure.arrays:
            structure.set_array("representationsshow", np.ones(self.natoms))

        return structure

    @observe("structure")
    def _observe_structure(self, change):
        """Update displayed_structure trait after the structure trait has been modified."""

        if change["new"] is not None:
            self.set_trait("displayed_structure", change["new"].repeat(self.supercell))
            self.set_trait("cell", change["new"].cell)
        else:
            self.set_trait("displayed_structure", None)
            self.set_trait("cell", None)

    @observe("displayed_structure")
    def _observe_displayed_structure(self, change):
        """Update the view if displayed_structure trait was modified."""
        if change["new"] is not None:
            self._viewer.add_component(
                nglview.ASEStructure(self.displayed_structure),
                default_representation=False,
                name="Structure",
            )
            self.update_representations()
        # not needed for the moment, actions are defined in the editors functions
        # to avoid unnecessary updates
        # reactivation would require some care

    def d_from(self, operand):
        point = np.array([float(i) for i in operand[1:-1].split(",")])
        return np.linalg.norm(self.structure.positions - point, axis=1)

    def name_operator(self, operand):
        """Defining the name operator which will handle atom kind names."""
        if operand.startswith("[") and operand.endswith("]"):
            names = operand[1:-1].split(",")
        elif not operand.endswith("[") and not operand.startswith("]"):
            names = [operand]
        symbols = self.structure.get_chemical_symbols()
        return np.array([i for i, val in enumerate(symbols) if val in names])

    def not_operator(self, operand):
        """Reverting the selected atoms."""
        if operand.startswith("[") and operand.endswith("]"):
            names = operand[1:-1].split(",")
        elif not operand.endswith("[") and not operand.startswith("]"):
            names = [operand]
        return (
            "["
            + ",".join(list(set(self.structure.get_chemical_symbols()) - set(names)))
            + "]"
        )

    def parse_advanced_sel(self, condition=None):
        """Apply advanced selection specified in the text field."""

        def addition(opa, opb):
            return opa + opb

        def subtraction(opa, opb):
            return opa - opb

        def mult(opa, opb):
            return opa * opb

        def division(opa, opb):
            if isinstance(opb, type(np.array([]))):
                if any(np.abs(opb) < 0.0001):
                    return np.array([])
            elif np.abs(opb) < 0.0001:
                return np.array([])
            return opa / opb

        def power(opa, opb):
            return opa**opb

        def greater(opa, opb):
            return np.where(opa > opb)[0]

        def lower(opa, opb):
            return np.where(opa < opb)[0]

        def equal(opa, opb):
            return np.where(opa == opb)[0]

        def notequal(opa, opb):
            return np.where(opa != opb)[0]

        def greatereq(opa, opb):
            return np.where(opa >= opb)[0]

        def lowereq(opa, opb):
            return np.where(opa <= opb)[0]

        def intersec(opa, opb):
            return np.intersect1d(opa, opb)

        def union(opa, opb):
            return np.union1d(opa, opb)

        operandsdict = {
            "x": self.structure.positions[:, 0],
            "y": self.structure.positions[:, 1],
            "z": self.structure.positions[:, 2],
            "id": np.array([atom.index + 1 for atom in self.structure]),
        }

        operatorsdict = {
            ">": {
                "function": greater,
                "priority": 0,
                "nargs": 2,
            },
            "<": {
                "function": lower,
                "priority": 0,
                "nargs": 2,
            },
            ">=": {
                "function": greatereq,
                "priority": 0,
                "nargs": 2,
            },
            "<=": {
                "function": lowereq,
                "priority": 0,
                "nargs": 2,
            },
            "and": {
                "function": intersec,
                "priority": -1,
                "nargs": 2,
            },
            "or": {
                "function": union,
                "priority": -2,
                "nargs": 2,
            },
            "+": {
                "function": addition,
                "priority": 1,
                "nargs": 2,
            },
            "-": {
                "function": subtraction,
                "priority": 1,
                "nargs": 2,
            },
            "*": {
                "function": mult,
                "priority": 2,
                "nargs": 2,
            },
            "/": {
                "function": division,
                "priority": 2,
                "nargs": 2,
            },
            "^": {
                "function": power,
                "priority": 3,
                "nargs": 2,
            },
            "==": {
                "function": equal,
                "priority": 0,
                "nargs": 2,
            },
            "!=": {
                "function": notequal,
                "priority": 0,
                "nargs": 2,
            },
            "d_from": {
                "function": self.d_from,
                "priority": 11,
                "nargs": 1,
            },  # At the moment the priority is not used.
            "name": {
                "function": self.name_operator,
                "priority": 9,
                "nargs": 1,
            },  # When changed, this should be re-assesed.
            "not": {
                "function": self.not_operator,
                "priority": 10,
                "nargs": 1,
            },
        }

        rpn = ReversePolishNotation(
            operators=operatorsdict, additional_operands=operandsdict
        )
        return list(rpn.execute(expression=condition))

    def create_selection_info(self):
        """Create information to be displayed with selected atoms"""
        if not self.selection:
            return ""

        def print_pos(pos):
            return " ".join([str(i) for i in pos.round(2)])

        def add_info(indx, atom):
            id_string = "Id:"
            if indx >= self.natoms:
                id_string = "Id-x" + str(int(indx / self.natoms))
            return f"{id_string} {indx + 1}; Symbol: {atom.symbol}; Coordinates: ({print_pos(atom.position)})<br>"

        # Find geometric center.
        geom_center = print_pos(
            np.average(self.displayed_structure[self.selection].get_positions(), axis=0)
        )

        # Report coordinates.
        if len(self.selection) == 1:
            return add_info(
                self.selection[0], self.displayed_structure[self.selection[0]]
            )

        # Report coordinates, distance and center.
        if len(self.selection) == 2:
            info = ""
            info += add_info(
                self.selection[0], self.displayed_structure[self.selection[0]]
            )
            info += add_info(
                self.selection[1], self.displayed_structure[self.selection[1]]
            )
            dist = self.displayed_structure.get_distance(*self.selection)
            distv = self.displayed_structure.get_distance(*self.selection, vector=True)
            info += f"Distance: {dist:.2f} ({print_pos(distv)})<br>Geometric center: ({geom_center})"
            return info

        info_natoms_geo_center = (
            f"{len(self.selection)} atoms selected<br>Geometric center: ({geom_center})"
        )

        # Report angle geometric center and normal.
        if len(self.selection) == 3:
            angle = self.displayed_structure.get_angle(*self.selection).round(2)
            normal = np.cross(
                *self.structure.get_distances(
                    self.selection[1],
                    [self.selection[0], self.selection[2]],
                    mic=False,
                    vector=True,
                )
            )
            normal = normal / np.linalg.norm(normal)
            return f"{info_natoms_geo_center}<br>Angle: {angle}<br>Normal: ({print_pos(normal)})"

        # Report dihedral angle and geometric center.
        if len(self.selection) == 4:
            try:
                dihedral = (
                    self.displayed_structure.get_dihedral(self.selection) * 180 / np.pi
                )
                dihedral_str = f"{dihedral:.2f}"
            except ZeroDivisionError:
                dihedral_str = "nan"
            return f"{info_natoms_geo_center}<br>Dihedral angle: {dihedral_str}"

        return info_natoms_geo_center

    @observe("selection_adv")
    def _observe_selection_adv(self, _=None):
        """Apply the advanced boolean atom selection"""
        try:
            sel = [int(i) for i in self.parse_advanced_sel(condition=self.selection_adv) if self.structure.arrays['representationsshow'][i]]
            self.selection = sel
            self._selected_atoms.value = list_to_string_range(sel, shift=1)
            self.wrong_syntax.layout.visibility = "hidden"
            self.apply_selection()
        except (IndexError, TypeError, AttributeError):
            self.wrong_syntax.layout.visibility = "visible"

    @observe("selection")
    def _observe_selection_2(self, _=None):
        self.selection_info.value = self.create_selection_info()


@register_viewer_widget("data.folder.FolderData.")
class FolderDataViewer(ipw.VBox):
    """Viewer class for FolderData object.

    :param folder: FolderData object to be viewed
    :type folder: FolderData
    :param downloadable: If True, add link/button to download the content of the selected file in the folder
    :type downloadable: bool"""

    def __init__(self, folder, downloadable=True, **kwargs):
        self._folder = folder
        self.files = ipw.Dropdown(
            options=[obj.name for obj in self._folder.list_objects()],
            description="Select file:",
        )
        self.text = ipw.Textarea(
            value="",
            description="File content:",
            layout={"width": "900px", "height": "300px"},
            disabled=False,
        )
        self.change_file_view()
        self.files.observe(self.change_file_view, names="value")
        children = [self.files, self.text]
        if downloadable:
            self.download_btn = ipw.Button(description="Download")
            self.download_btn.on_click(self.download)
            children.append(self.download_btn)
        super().__init__(children, **kwargs)

    def change_file_view(self, change=None):  # pylint: disable=unused-argument
        with self._folder.open(self.files.value) as fobj:
            self.text.value = fobj.read()

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare for downloading."""
        from IPython.display import Javascript

        payload = base64.b64encode(
            self._folder.get_object_content(self.files.value).encode()
        ).decode()
        javas = Javascript(
            """
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(
                payload=payload, filename=self.files.value
            )
        )
        display(javas)


@register_viewer_widget("data.array.bands.BandsData.")
class BandsDataViewer(ipw.VBox):
    """Viewer class for BandsData object.

    :param bands: BandsData object to be viewed
    :type bands: BandsData"""

    def __init__(self, bands, **kwargs):
        from bokeh.io import output_notebook, show
        from bokeh.models import Span
        from bokeh.plotting import figure

        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            plot_info = bands._get_bandplot_data(
                cartesian=True, join_symbol="|"
            )  # pylint: disable=protected-access
            # Extract relevant data
            y_data = plot_info["y"].transpose().tolist()
            x_data = [plot_info["x"] for i in range(len(y_data))]
            labels = plot_info["labels"]
            # Create the figure
            plot = figure(y_axis_label=f"Dispersion ({bands.units})")
            plot.multi_line(
                x_data, y_data, line_width=2, line_color="red"
            )  # pylint: disable=too-many-function-args
            plot.xaxis.ticker = [label[0] for label in labels]
            # This trick was suggested here: https://github.com/bokeh/bokeh/issues/8166#issuecomment-426124290
            plot.xaxis.major_label_overrides = {
                int(label[0]) if label[0].is_integer() else label[0]: label[1]
                for label in labels
            }
            # Add vertical lines
            plot.renderers.extend(
                [
                    Span(
                        location=label[0],
                        dimension="height",
                        line_color="black",
                        line_width=3,
                    )
                    for label in labels
                ]
            )
            show(plot)
        children = [out]
        super().__init__(children, **kwargs)


@register_viewer_widget("process.calculation.calcfunction.CalcFunctionNode.")
@register_viewer_widget("process.calculation.calcjob.CalcJobNode.")
@register_viewer_widget("process.workflow.workfunction.WorkFunctionNode.")
@register_viewer_widget("process.workflow.workchain.WorkChainNode.")
class ProcessNodeViewerWidget(ipw.HTML):
    def __init__(self, process, **kwargs):
        self.process = process

        # Displaying reports only from the selected process,
        # NOT from its descendants.
        report = get_workchain_report(self.process, "REPORT", max_depth=1)
        # Filter out the first column with dates
        filtered_report = re.sub(
            r"^[0-9]{4}.*\| ([A-Z]+)\]", r"\1", report, flags=re.MULTILINE
        )
        header = f"""
            Process {process.process_label},
            State: {formatting.format_process_state(process.process_state.value)},
            UUID: {process.uuid} (pk: {process.pk})<br>
            Started {formatting.format_relative_time(process.ctime)},
            Last modified {formatting.format_relative_time(process.mtime)}<br>
        """
        self.value = f"{header}<pre>{filtered_report}</pre>"

        super().__init__(**kwargs)
