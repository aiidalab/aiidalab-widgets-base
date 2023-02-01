"""Jupyter viewers for AiiDA data objects."""
# pylint: disable=no-self-use

import base64
import copy
import re
import warnings

import ipywidgets as ipw
import nglview
import numpy as np
import shortuuid
import spglib
import traitlets
from aiida.cmdline.utils.common import get_workchain_report
from aiida.orm import Node
from aiida.tools.query import formatting
from ase import Atoms, neighborlist
from ase.cell import Cell
from IPython.display import clear_output, display
from matplotlib.colors import to_rgb
from numpy.linalg import norm
from traitlets import (
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

AIIDA_VIEWER_MAPPING = {}


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
    except (KeyError) as exc:
        if obj.node_type in str(exc):
            warnings.warn(
                "Did not find an appropriate viewer for the {} object. Returning the object "
                "itself.".format(type(obj))
            )
            return obj
        raise
    else:
        return _viewer(obj, downloadable=downloadable, **kwargs)


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


@register_viewer_widget("data.core.dict.Dict.")
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


class NglViewerRepresentation(ipw.HBox):
    """Representation for StructureData in nglviewer"""

    master_class = None

    def __init__(self, uuid=None, indices=None, deletable=True, array_threshold=1.0):
        """Initialize the representation.

        uuid: str
            Unique identifier for the representation.
        indices: list
            List of indices to be displayed.
        deletable: bool
            If True, add a button to delete the representation.
        array_threshold: float
            Threshold for displaying atoms based on the values of _aiidalab_viewer_representation_* arrays.
        """

        self.array_threshold = array_threshold
        self.uuid = uuid or f"_aiidalab_viewer_representation_{shortuuid.uuid()}"

        self.show = ipw.Checkbox(
            value=True,
            layout={"width": "40px"},
            style={"description_width": "0px"},
            disabled=False,
        )

        self.selection = ipw.Text(
            value=list_to_string_range(indices, shift=1) if indices is not None else "",
            layout={"width": "80px"},
            style={"description_width": "0px"},
        )
        self.type = ipw.Dropdown(
            options=["ball+stick", "spacefill"],
            value="ball+stick",
            disabled=False,
            layout={"width": "100px"},
            style={"description_width": "0px"},
        )
        self.size = ipw.FloatText(
            value=3,
            layout={"width": "40px"},
            style={"description_width": "0px"},
        )
        self.color = ipw.Dropdown(
            options=["element", "red", "green", "blue", "yellow", "orange", "purple"],
            value="element",
            disabled=False,
            layout={"width": "80px"},
            style={"description_width": "initial"},
        )

        # Delete button.
        self.delete_button = ipw.Button(
            description="",
            icon="trash",
            button_style="danger",
            layout={
                "width": "50px",
                "visibility": "visible" if deletable else "hidden",
            },
            style={"description_width": "initial"},
        )
        self.delete_button.on_click(self.delete_myself)

        super().__init__(
            children=[
                self.show,
                self.selection,
                self.type,
                self.size,
                self.color,
                self.delete_button,
            ]
        )

    def delete_myself(self, _):
        self.master_class.delete_representation(self)

    def sync_myself_to_array_from_atoms_object(self, structure):
        """Update representation from the structure object."""
        if structure:
            if self.uuid in structure.arrays:
                self.selection.value = list_to_string_range(
                    np.where(self.atoms_in_representaion(structure))[0], shift=1
                )
                return True
        return False

    def add_myself_to_atoms_object(self, structure):
        """Add representation array to the structure object. If the array already exists, update it."""
        if structure:
            array_representation = np.full(len(structure), -1)
            selection = np.array(
                string_range_to_list(self.selection.value, shift=-1)[0]
            )
            # Only attempt to display the existing atoms.
            array_representation[selection[selection < len(structure)]] = 1
            structure.set_array(self.uuid, array_representation)
            return True
        return False

    def atoms_in_representaion(self, structure=None):
        """Return an array of booleans indicating which atoms are present in the representation."""
        if structure:
            if self.uuid in structure.arrays:
                return structure.arrays[self.uuid] >= self.array_threshold
        return False


class _StructureDataBaseViewer(ipw.VBox):
    """Base viewer class for AiiDA structure or trajectory objects.

    :param configure_view: If True, add configuration tabs (deprecated)
    :type configure_view: bool
    :param configuration_tabs: List of configuration tabs (default: ["Selection", "Appearance", "Cell", "Download"])
    :type configure_view: list
    :param default_camera: default camera (orthographic|perspective), can be changed in the Appearance tab
    :type default_camera: string

    """

    _all_representations = traitlets.List()
    natoms = Int()
    input_selection = List(Int, allow_none=True)
    selection = List(Int)
    displayed_selection = List(Int)
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
        self.natoms = 0

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
            description="Select atoms:",
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
        clear_selection.on_click(
            lambda _: self.set_trait("displayed_selection", [])
        )  # lambda cannot contain assignments

        # 5. Button to apply selection
        apply_displayed_selection = ipw.Button(description="Apply selection")
        apply_displayed_selection.on_click(self.apply_displayed_selection)

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
                ipw.HBox(
                    [copy_to_clipboard, clear_selection, apply_displayed_selection]
                ),
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
            ipw.BoundedIntText(value=1, min=1, layout={"width": "40px"}),
            ipw.BoundedIntText(value=1, min=1, layout={"width": "40px"}),
            ipw.BoundedIntText(value=1, min=1, layout={"width": "40px"}),
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
        self.representations_header = ipw.HBox(
            [
                ipw.HTML(
                    """<p style="text-align:center">Show</p>""",
                    layout={"width": "40px"},
                ),
                ipw.HTML(
                    """<p style="text-align:center">Atoms</p>""",
                    layout={"width": "80px"},
                ),
                ipw.HTML(
                    """<p style="text-align:center">Type</p>""",
                    layout={"width": "100px"},
                ),
                ipw.HTML(
                    """<p style="text-align:center">Size</p>""",
                    layout={"width": "40px"},
                ),
                ipw.HTML(
                    """<p style="text-align:center">Color</p>""",
                    layout={"width": "80px"},
                ),
                ipw.HTML(
                    """<p style="text-align:center">Delete</p>""",
                    layout={"width": "50px"},
                ),
            ]
        )
        self.atoms_not_represented = ipw.HTML()
        add_new_representation_button = ipw.Button(
            description="Add representation", button_style="info"
        )
        add_new_representation_button.on_click(self._add_representation)

        apply_representations = ipw.Button(description="Apply representations")
        apply_representations.on_click(self._apply_representations)
        self.representation_output = ipw.VBox()

        # The default representation is always present and cannot be deleted.
        # Moreover, it always shows new atoms due to the array_threshold=0.
        self._all_representations = [
            NglViewerRepresentation(
                uuid="_aiidalab_viewer_representation_default",
                deletable=False,
                array_threshold=0,
            )
        ]
        return ipw.VBox(
            [
                supercell_selector,
                background_color,
                camera_type,
                self.representations_header,
                self.representation_output,
                self.atoms_not_represented,
                ipw.HBox([apply_representations, add_new_representation_button]),
                center_button,
            ]
        )

    def _add_representation(self, _=None, uuid=None, indices=None):
        """Add a representation to the list of representations."""
        self._all_representations = self._all_representations + [
            NglViewerRepresentation(uuid=uuid, indices=indices)
        ]
        self._apply_representations()

    def delete_representation(self, representation):
        try:
            index = self._all_representations.index(representation)
        except ValueError:
            self.representation_add_message.message = f"""<span style="color:red">Error:</span> Rep. {representation} not found."""
            return

        self._all_representations = (
            self._all_representations[:index] + self._all_representations[index + 1 :]
        )

        if representation.uuid in self.structure.arrays:
            del self.structure.arrays[representation.uuid]
        del representation
        self._apply_representations()

    @observe("_all_representations")
    def _observe_all_representations(self, change):
        """Update the list of representations."""
        self.representation_output.children = change["new"]
        if change["new"]:
            self._all_representations[-1].master_class = self

    def _get_representation_parameters(self, indices, representation):
        """Return the parameters dictionary of a representation."""
        params = {
            "type": representation.type.value,
            "params": {
                "sele": self._list_to_nglview(indices),
                "opacity": 1,
                "color": representation.color.value,
            },
        }
        if representation.type.value == "ball+stick":
            params["params"]["aspectRatio"] = representation.size.value
        else:
            params["params"]["radiusScale"] = 0.1 * representation.size.value

        return params

    def _apply_representations(self, change=None):
        """Apply the representations to the displayed structure."""
        rep_uuids = []

        # Representation can only be applied if a structure is present.
        if self.structure is None:
            return

        # Add existing representations to the structure.
        for representation in self._all_representations:
            representation.add_myself_to_atoms_object(self.structure)
            rep_uuids.append(representation.uuid)

        # Remove missing representations from the structure.
        for array in self.structure.arrays:
            if (
                array.startswith("_aiidalab_viewer_representation_")
                and array not in rep_uuids
            ):
                del self.structure.arrays[array]
        self._observe_structure({"new": self.structure})
        self._check_missing_atoms_in_representations()

    def _check_missing_atoms_in_representations(self):
        missing_atoms = np.zeros(self.natoms)
        for rep in self._all_representations:
            missing_atoms += rep.atoms_in_representaion(self.structure)
        missing_atoms = np.where(missing_atoms == 0)[0]
        if len(missing_atoms) > 0:
            self.atoms_not_represented.value = (
                "Atoms excluded from representations: "
                + list_to_string_range(list(missing_atoms), shift=1)
            )
        else:
            self.atoms_not_represented.value = ""

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

        if not isinstance(self.displayed_structure, Atoms):
            return

        self.render_btn.disabled = True
        omat = np.array(self._viewer._camera_orientation).reshape(4, 4).transpose()

        zfactor = norm(omat[0, 0:3])
        omat[0:3, 0:3] = omat[0:3, 0:3] / zfactor

        bb = copy.deepcopy(self.displayed_structure)
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

        cutoff = neighborlist.natural_cutoffs(
            bb
        )  # Takes the cutoffs from the ASE database
        neighbor_list = neighborlist.NeighborList(
            cutoff, self_interaction=False, bothways=False
        )
        neighbor_list.update(bb)
        matrix = neighbor_list.get_connectivity_matrix()

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
            # Did not click on atom:
            if "atom1" not in self._viewer.picked.keys():
                return

            index = self._viewer.picked["atom1"]["index"]

            displayed_selection = self.displayed_selection.copy()
            if displayed_selection:
                if index not in displayed_selection:
                    displayed_selection.append(index)
                else:
                    displayed_selection.remove(index)
            else:
                displayed_selection = [index]
            self.displayed_selection = displayed_selection

    def _list_to_nglview(self, the_list):
        """Converts a list of structures to a nglview widget"""
        selection = "none"
        if len(the_list):
            selection = "@" + ",".join(map(str, the_list))
        return selection

    def highlight_atoms(
        self,
        vis_list,
    ):
        """Highlighting atoms according to the provided list."""
        if not hasattr(self._viewer, "component_0"):
            return

        # Create the dictionaries for highlight_representations.
        for i, representation in enumerate(self._all_representations):

            # First remove the previous highlight_representation.
            self._viewer._remove_representations_by_name(
                repr_name=f"highlight_representation_{i}", component=0
            )

            # Then add the new one if needed.
            indices = np.intersect1d(
                vis_list,
                np.where(
                    representation.atoms_in_representaion(self.displayed_structure)
                )[0],
            )
            if len(indices) > 0:
                params = self._get_representation_parameters(
                    indices, self._all_representations[i]
                )
                params["params"]["name"] = f"highlight_representation_{i}"
                params["params"]["opacity"] = 0.3
                params["params"]["component_index"] = 0
                if "radiusScale" in params["params"]:
                    params["params"]["radiusScale"] *= 1.4
                else:
                    params["params"]["aspectRatio"] *= 1.4

                # Use directly the remote call for more flexibility.
                self._viewer._remote_call(
                    "addRepresentation",
                    target="compList",
                    args=[params["type"]],
                    kwargs=params["params"],
                )

    def remove_viewer_components(self, c=None):
        if hasattr(self._viewer, "component_0"):
            self._viewer.component_0.clear_representations()
            cid = self._viewer.component_0.id
            self._viewer.remove_component(cid)

    @default("supercell")
    def _default_supercell(self):
        return [1, 1, 1]

    @observe("input_selection")
    def _observe_input_selection(self, value):
        if value["new"] is None:
            return

        # Exclude everything that is beyond the total number of atoms.
        selection_list = [x for x in value["new"] if x < self.natoms]

        # In the case of a super cell, we need to multiply the selection as well
        multiplier = sum(self.supercell) - 2
        selection_list = [
            x + self.natoms * i for x in selection_list for i in range(multiplier)
        ]

        self.displayed_selection = selection_list

    @observe("displayed_selection")
    def _observe_displayed_selection(self, _=None):
        seen = set()
        seq = [x % self.natoms for x in self.displayed_selection]
        self.selection = [x for x in seq if not (x in seen or seen.add(x))]
        self.highlight_atoms(self.displayed_selection)

    def apply_displayed_selection(self, _=None):
        """Apply selection specified in the text field."""
        expanded_selection, syntax_ok = string_range_to_list(
            self._selected_atoms.value, shift=-1
        )
        if not syntax_ok:
            try:
                sel = self._parse_advanced_selection(
                    condition=self._selected_atoms.value
                )
                sel = list_to_string_range(sel, shift=1)
                expanded_selection, syntax_ok = string_range_to_list(sel, shift=-1)
            except (IndexError, TypeError, AttributeError):
                syntax_ok = False
                self.wrong_syntax.layout.visibility = "visible"

        if syntax_ok:
            self.wrong_syntax.layout.visibility = "hidden"
            self.displayed_selection = expanded_selection
        else:
            self.wrong_syntax.layout.visibility = "visible"

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


@register_viewer_widget("data.core.cif.CifData.")
@register_viewer_widget("data.core.structure.StructureData.")
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.natoms = len(self.structure) if self.structure else 0

    @observe("supercell")
    def _observe_supercell(self, _=None):
        if self.structure is not None:
            self.set_trait(
                "displayed_structure", None
            )  # To make sure the structure is always updated.
            self.set_trait("displayed_structure", self.structure.repeat(self.supercell))

    @validate("structure")
    def _valid_structure(self, change):
        """Update structure."""
        structure = change["value"]
        # If no structure is provided, the rest of the code can be skipped.
        if structure is None:
            return None
        if isinstance(structure, Atoms):
            self.pk = None
        elif isinstance(structure, Node):
            self.pk = structure.pk
            structure = structure.get_ase()

            raise TypeError(
                f"Unsupported type {type(structure)}, structure must be one of the following types: "
                "ASE Atoms object, AiiDA CifData or StructureData."
            )
        if "_aiidalab_viewer_representation_default" not in structure.arrays:
            structure.set_array(
                "_aiidalab_viewer_representation_default", np.zeros(len(structure))
            )
        return structure

    @observe("structure")
    def _observe_structure(self, change=None):
        """Update displayed_structure trait after the structure trait has been modified."""
        structure = change["new"]

        self._viewer.clear_representations(component=0)

        if structure:
            self.natoms = len(structure)
            # Make sure that the representation arrays from structure are present in the viewer.
            uuids = [
                uuid
                for uuid in structure.arrays
                if uuid.startswith("_aiidalab_viewer_representation_")
            ]
            rep_uuids = [rep.uuid for rep in self._all_representations]
            for uuid in uuids:
                try:
                    index = rep_uuids.index(uuid)
                    self._all_representations[
                        index
                    ].sync_myself_to_array_from_atoms_object(structure)
                except ValueError:
                    self._add_representation(
                        uuid=uuid,
                        indices=np.where(structure.arrays[self.uuid] >= 1.0)[0],
                    )
            self._observe_supercell()  # To trigger an update of the displayed structure
            self.set_trait("cell", structure.cell)
        else:
            self.set_trait("displayed_structure", None)
            self.set_trait("cell", None)
            self.natoms = 0

    @observe("displayed_structure")
    def _observe_displayed_structure(self, change):
        """Update the view if displayed_structure trait was modified."""
        with self.hold_trait_notifications():
            self.remove_viewer_components()
            if change["new"]:
                self._viewer.add_component(
                    nglview.ASEStructure(self.displayed_structure),
                    default_representation=False,
                    name="Structure",
                )
                representation_parameters = []
                for representation in self._all_representations:
                    if not representation.show.value:
                        continue
                    indices = np.where(
                        representation.atoms_in_representaion(self.displayed_structure)
                    )[0]
                    representation_parameters.append(
                        self._get_representation_parameters(indices, representation)
                    )

                self._viewer.set_representations(representation_parameters, component=0)
                self._viewer.add_unitcell()
                self._viewer.center()
        self.displayed_selection = []

    def d_from(self, operand):
        point = np.array([float(i) for i in operand[1:-1].split(",")])
        return np.linalg.norm(self.displayed_structure.positions - point, axis=1)

    def name_operator(self, operand):
        """Defining the name operator which will handle atom kind names."""
        if operand.startswith("[") and operand.endswith("]"):
            names = operand[1:-1].split(",")
        elif not operand.endswith("[") and not operand.startswith("]"):
            names = [operand]
        symbols = self.displayed_structure.get_chemical_symbols()
        return np.array([i for i, val in enumerate(symbols) if val in names])

    def not_operator(self, operand):
        """Reverting the selected atoms."""
        if operand.startswith("[") and operand.endswith("]"):
            names = operand[1:-1].split(",")
        elif not operand.endswith("[") and not operand.startswith("]"):
            names = [operand]
        return (
            "["
            + ",".join(
                list(set(self.displayed_structure.get_chemical_symbols()) - set(names))
            )
            + "]"
        )

    def _parse_advanced_selection(self, condition=None):
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
            "x": self.displayed_structure.positions[:, 0],
            "y": self.displayed_structure.positions[:, 1],
            "z": self.displayed_structure.positions[:, 2],
            "id": np.array([atom.index + 1 for atom in self.displayed_structure]),
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

        if not self.displayed_selection:
            return ""

        def print_pos(pos):
            return " ".join([str(i) for i in pos.round(2)])

        def add_info(indx, atom):
            return f"<p>Id: {indx + 1}; Symbol: {atom.symbol}; Coordinates: ({print_pos(atom.position)})</p>"

        # Unit and displayed cell atoms' selection.
        info = (
            f"<p>Selected atoms: {list_to_string_range(self.displayed_selection, shift=1)}</p>"
            + f"<p>Selected unit cell atoms: {list_to_string_range(self.selection, shift=1)}</p>"
        )
        # Find geometric center.
        geom_center = print_pos(
            np.average(
                self.displayed_structure[self.displayed_selection].get_positions(),
                axis=0,
            )
        )

        # Report coordinates.
        if len(self.displayed_selection) == 1:
            info += add_info(
                self.displayed_selection[0],
                self.displayed_structure[self.displayed_selection[0]],
            )

        # Report coordinates, distance and center.
        elif len(self.displayed_selection) == 2:
            info += add_info(
                self.displayed_selection[0],
                self.displayed_structure[self.displayed_selection[0]],
            )
            info += add_info(
                self.displayed_selection[1],
                self.displayed_structure[self.displayed_selection[1]],
            )
            dist = self.displayed_structure.get_distance(*self.displayed_selection)
            distv = self.displayed_structure.get_distance(
                *self.displayed_selection, vector=True
            )
            info += f"<p>Distance: {dist:.2f} ({print_pos(distv)})</p>"

        # Report angle geometric center and normal.
        elif len(self.displayed_selection) == 3:
            angle = self.displayed_structure.get_angle(*self.displayed_selection).round(
                2
            )
            normal = np.cross(
                *self.displayed_structure.get_distances(
                    self.displayed_selection[1],
                    [self.displayed_selection[0], self.displayed_selection[2]],
                    mic=False,
                    vector=True,
                )
            )
            normal = normal / np.linalg.norm(normal)
            info += f"<p>Angle: {angle}, Normal: ({print_pos(normal)})</p>"

        # Report dihedral angle and geometric center.
        elif len(self.displayed_selection) == 4:
            try:
                dihedral = self.displayed_structure.get_dihedral(
                    *self.displayed_selection
                )
                dihedral_str = f"{dihedral:.2f}"
            except ZeroDivisionError:
                dihedral_str = "nan"
            info += f"<p>Dihedral angle: {dihedral_str}</p>"

        return (
            info
            + f"<p>Geometric center: ({geom_center})</p>"
            + f"<p>{len(self.displayed_selection)} atoms selected</p>"
        )

    @observe("displayed_selection")
    def _observe_displayed_selection_2(self, _=None):
        self.selection_info.value = self.create_selection_info()


@register_viewer_widget("data.core.folder.FolderData.")
class FolderDataViewer(ipw.VBox):
    """Viewer class for FolderData object.

    :param folder: FolderData object to be viewed
    :type folder: FolderData
    :param downloadable: If True, add link/button to download the content of the selected file in the folder
    :type downloadable: bool"""

    def __init__(self, folder, downloadable=True, **kwargs):
        self._folder = folder
        self.files = ipw.Dropdown(
            options=[obj.name for obj in self._folder.base.repository.list_objects()],
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
        with self._folder.base.repository.open(self.files.value) as fobj:
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


@register_viewer_widget("data.core.array.bands.BandsData.")
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
