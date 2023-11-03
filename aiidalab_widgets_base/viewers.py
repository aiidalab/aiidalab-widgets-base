"""Jupyter viewers for AiiDA data objects."""
# pylint: disable=no-self-use

import base64
import re
import warnings
from copy import deepcopy

import ase
import ipywidgets as ipw
import nglview
import numpy as np
import spglib
import traitlets as tl
import vapory
from aiida import cmdline, orm, tools
from IPython.display import clear_output, display
from matplotlib.colors import to_rgb

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


def viewer(obj, **kwargs):
    """Display AiiDA data types in Jupyter notebooks.

    Returns the object itself if the viewer wasn't found."""
    if not isinstance(obj, orm.Node):  # only working with AiiDA nodes
        warnings.warn(
            f"This viewer works only with AiiDA objects, got {type(obj)}", stacklevel=2
        )
        return obj

    if obj.node_type in AIIDA_VIEWER_MAPPING:
        _viewer = AIIDA_VIEWER_MAPPING[obj.node_type]
        return _viewer(obj, **kwargs)
    else:
        # No viewer registered for this type, return object itself
        return obj


class AiidaNodeViewWidget(ipw.VBox):
    node = tl.Instance(orm.Node, allow_none=True)

    def __init__(self, **kwargs):
        self._output = ipw.Output()
        super().__init__(
            children=[
                self._output,
            ],
            **kwargs,
        )

    @tl.observe("node")
    def _observe_node(self, change):
        if change["new"] != change["old"]:
            with self._output:
                clear_output()
                if change["new"]:
                    display(viewer(change["new"]))


@register_viewer_widget("data.core.dict.Dict.")
class DictViewer(ipw.VBox):
    value = tl.Unicode()
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
            self.value += f"""Download table in csv format: <a download="{fname}"
            href="data:text/csv;base64,{payload}" target="_blank">{fname}</a>"""

        super().__init__([self.widget], **kwargs)


class _StructureDataBaseViewer(ipw.VBox):
    """Base viewer class for AiiDA structure or trajectory objects.

    :param configure_view: If True, add configuration tabs (deprecated)
    :type configure_view: bool
    :param configuration_tabs: List of configuration tabs (default: ["Selection", "Appearance", "Cell", "Download"])
    :type configure_view: list
    :param default_camera: default camera (orthographic|perspective), can be changed in the Appearance tab
    :type default_camera: string

    """

    input_selection = tl.List(tl.Int(), allow_none=True)
    selection = tl.List(tl.Int())
    displayed_selection = tl.List(tl.Int())
    supercell = tl.List(tl.Int())
    cell = tl.Instance(ase.cell.Cell, allow_none=True)
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
                stacklevel=2,
            )
            if not configure_view:
                configuration_tabs.clear()

        # Constructing configuration box
        if configuration_tabs is None:
            configuration_tabs = ["Selection", "Appearance", "Cell", "Download"]
        if len(configuration_tabs) != 0:
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
        tl.link((self._selected_atoms, "value"), (copy_to_clipboard, "value"))

        # 3. Informing about wrong syntax.
        self.wrong_syntax = ipw.HTML(
            value="""<i class="fa fa-times" style="color:red;font-size:2em;" ></i> wrong syntax""",
            layout={"visibility": "hidden"},
        )

        # 4. Button to clear selection.
        clear_selection = ipw.Button(description="Clear selection")
        # clear_selection.on_click(lambda _: self.set_trait('selection', list()))  # lambda cannot contain assignments
        clear_selection.on_click(
            lambda _: (
                self.set_trait("displayed_selection", []),
                self.set_trait("selection", []),
            )
        )

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
        tl.link((background_color, "value"), (self._viewer, "background"))
        background_color.value = "white"

        # 3. Camera switcher
        camera_type = ipw.ToggleButtons(
            options=[("Orthographic", "orthographic"), ("Perspective", "perspective")],
            description="Camera type:",
            value=self._viewer.camera,
            layout={"align_self": "flex-start"},
            style={"button_width": "115.5px"},
        )

        def change_camera(change):
            self._viewer.camera = change["new"]

        camera_type.observe(change_camera, names="value")

        # 4. Center button.
        center_button = ipw.Button(description="Center molecule")
        center_button.on_click(lambda c: self._viewer.center())

        return ipw.VBox(
            [supercell_selector, background_color, camera_type, center_button]
        )

    @tl.observe("cell")
    def _observe_cell(self, _=None):
        # Updtate the Cell and Periodicity.
        if self.cell:
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

            periodicity_map = {
                (True, True, True): "xyz",
                (True, False, False): "x",
                (False, True, False): "y",
                (False, False, True): "z",
                (True, True, False): "xy",
                (True, False, True): "xz",
                (False, True, True): "yz",
                (False, False, False): "-",
            }
            self.cell_spacegroup.value = f"Spacegroup: {symmetry_dataset['international']} (No.{symmetry_dataset['number']})"
            self.cell_hall.value = f"Hall: {symmetry_dataset['hall']} (No.{symmetry_dataset['hall_number']})"
            self.periodicity.value = (
                f"Periodicity: {periodicity_map[tuple(self.structure.pbc)]}"
            )
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

            self.cell_spacegroup.value = ""
            self.cell_hall.value = ""
            self.periodicity.value = ""

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
        self.periodicity = ipw.HTML()

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
                                self.periodicity,
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
            label="Extended xyz",
            # File extension and format may be different. Therefore, we define both.
            options=(
                ("xyz", {"extension": "xyz", "format": "xyz"}),
                ("cif", {"extension": "cif", "format": "cif"}),
                ("Extended xyz", {"extension": "xyz", "format": "extxyz"}),
                ("xsf", {"extension": "xsf", "format": "xsf"}),
            ),
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
        self.render_btn = ipw.Button(description="Render", icon="paint-brush")
        self.render_btn.on_click(self._render_structure)
        self.render_box = ipw.VBox(
            children=[ipw.Label("Render an image with POVRAY:"), self.render_btn]
        )

        return ipw.VBox([self.download_box, self.screenshot_box, self.render_box])

    def _render_structure(self, change=None):
        """Render the structure with POVRAY."""

        if not isinstance(self.displayed_structure, ase.Atoms):
            return

        self.render_btn.disabled = True
        omat = np.array(self._viewer._camera_orientation).reshape(4, 4).transpose()

        zfactor = np.linalg.norm(omat[0, 0:3])
        omat[0:3, 0:3] = omat[0:3, 0:3] / zfactor

        bb = deepcopy(self.displayed_structure)
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

        cutoff = ase.neighborlist.natural_cutoffs(
            bb
        )  # Takes the cutoffs from the ASE database
        neighbor_list = ase.neighborlist.NeighborList(
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
            bond = vapory.Cylinder(
                v1,
                midi,
                0.2,
                vapory.Pigment("color", np.array(Colors[i.symbol])),
                vapory.Finish("phong", 0.8, "reflection", 0.05),
            )
            bonds.append(bond)
            bond = vapory.Cylinder(
                v2,
                midi,
                0.2,
                vapory.Pigment("color", np.array(Colors[j.symbol])),
                vapory.Finish("phong", 0.8, "reflection", 0.05),
            )
            bonds.append(bond)

        edges = []
        for x, i in enumerate(vertices):
            for j in vertices[x + 1 :]:
                if (
                    np.linalg.norm(np.cross(i - j, vertices[1] - vertices[0])) < 0.001
                    or np.linalg.norm(np.cross(i - j, vertices[2] - vertices[0]))
                    < 0.001
                    or np.linalg.norm(np.cross(i - j, vertices[3] - vertices[0]))
                    < 0.001
                ):
                    edge = vapory.Cylinder(
                        i,
                        j,
                        0.06,
                        vapory.Texture(
                            vapory.Pigment(
                                "color", [212 / 255.0, 175 / 255.0, 55 / 255.0]
                            )
                        ),
                        vapory.Finish("phong", 0.9, "reflection", 0.01),
                    )
                    edges.append(edge)

        camera = vapory.Camera(
            "perspective",
            "location",
            [0, 0, -zfactor / 1.5],
            "look_at",
            [0.0, 0.0, 0.0],
        )
        light = vapory.LightSource([0, 0, -100.0], "color", [1.5, 1.5, 1.5])

        spheres = [
            vapory.Sphere(
                [i.x, i.y, i.z],
                Radius[i.symbol],
                vapory.Texture(vapory.Pigment("color", np.array(Colors[i.symbol]))),
                vapory.Finish("phong", 0.9, "reflection", 0.05),
            )
            for i in bb
        ]

        objects = (
            [light]
            + spheres
            + edges
            + bonds
            + [vapory.Background("color", np.array(to_rgb(self._viewer.background)))]
        )

        scene = vapory.Scene(camera, objects=objects)
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
        if "atom1" not in self._viewer.picked.keys():
            return  # did not click on atom
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

    def highlight_atoms(
        self,
        vis_list,
        color=DEFAULT_SELECTION_COLOR,
        size=DEFAULT_SELECTION_RADIUS,
        opacity=DEFAULT_SELECTION_OPACITY,
    ):
        """Highlighting atoms according to the provided list."""
        if not hasattr(self._viewer, "component_0"):
            return
        self._viewer._remove_representations_by_name(
            repr_name="selected_atoms"
        )  # pylint:disable=protected-access
        self._viewer.add_ball_and_stick(  # pylint:disable=no-member
            name="selected_atoms",
            selection=[] if vis_list is None else vis_list,
            color=color,
            aspectRatio=size,
            opacity=opacity,
        )

    @tl.default("supercell")
    def _default_supercell(self):
        return [1, 1, 1]

    @tl.observe("input_selection")
    def _observe_input_selection(self, value):
        if value["new"] is None:
            return

        # Exclude everything that is beyond the total number of atoms.
        selection_list = [x for x in value["new"] if x < self.natom]

        # In the case of a super cell, we need to multiply the selection as well
        multiplier = sum(self.supercell) - 2
        selection_list = [
            x + self.natom * i for x in selection_list for i in range(multiplier)
        ]

        self.displayed_selection = selection_list

    @tl.observe("displayed_selection")
    def _observe_displayed_selection(self, _=None):
        seen = set()
        seq = [x % self.natom for x in self.displayed_selection]
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
        payload = self._prepare_payload(self.file_format.value["format"])
        if payload is None:
            return
        suffix = f"pk-{self.pk}" if self.pk else "not-stored"
        self._download(
            payload=payload,
            filename=f"""structure-{suffix}.{self.file_format.value["extension"]}""",
        )

    @staticmethod
    def _download(payload, filename):
        """Download payload as a file named as filename."""
        from IPython.display import Javascript

        javas = Javascript(
            f"""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """
        )
        display(javas)

    def _prepare_payload(self, file_format=None):
        """Prepare binary information."""
        from tempfile import NamedTemporaryFile

        if not self.structure:
            return None

        file_format = file_format if file_format else self.file_format.value["format"]
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

    structure = tl.Union(
        [tl.Instance(ase.Atoms), tl.Instance(orm.Node)], allow_none=True
    )
    displayed_structure = tl.Instance(ase.Atoms, allow_none=True, read_only=True)
    pk = tl.Int(allow_none=True)

    def __init__(self, structure=None, **kwargs):
        super().__init__(**kwargs)
        self.structure = structure
        self.natom = len(self.structure) if self.structure is not None else 0

    @tl.observe("supercell")
    def repeat(self, _=None):
        if self.structure is not None:
            self.set_trait("displayed_structure", self.structure.repeat(self.supercell))

    @tl.validate("structure")
    def _valid_structure(self, change):  # pylint: disable=no-self-use
        """Update structure."""
        structure = change["value"]

        if structure is None:
            return None  # if no structure provided, the rest of the code can be skipped

        if isinstance(structure, ase.Atoms):
            self.pk = None
            return structure
        if isinstance(structure, orm.Node):
            self.pk = structure.pk
            return structure.get_ase()
        raise TypeError(
            f"Unsupported type {type(structure)}, structure must be one of the following types: "
            "ASE Atoms object, AiiDA CifData or StructureData."
        )

    @tl.observe("structure")
    def _observe_structure(self, change):
        """Update displayed_structure trait after the structure trait has been modified."""
        self.natom = len(self.structure) if self.structure is not None else 0
        # Remove the current structure(s) from the viewer.
        if change["new"] is not None:
            self.set_trait("displayed_structure", change["new"].repeat(self.supercell))
            self.set_trait("cell", change["new"].cell)
        else:
            self.set_trait("displayed_structure", None)
            self.set_trait("cell", None)

    @tl.observe("displayed_structure")
    def _update_structure_viewer(self, change):
        """Update the view if displayed_structure trait was modified."""
        with self.hold_trait_notifications():
            for (
                comp_id
            ) in self._viewer._ngl_component_ids:  # pylint: disable=protected-access
                self._viewer.remove_component(comp_id)
            self.displayed_selection = []
            if change["new"] is not None:
                self._viewer.add_component(nglview.ASEStructure(change["new"]))
                self._viewer.clear()
                self._viewer.add_ball_and_stick(
                    aspectRatio=4
                )  # pylint: disable=no-member
                self._viewer.add_unitcell()  # pylint: disable=no-member

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
        info_selected_atoms = (
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
            return info_selected_atoms + add_info(
                self.displayed_selection[0],
                self.displayed_structure[self.displayed_selection[0]],
            )

        # Report coordinates, distance and center.
        if len(self.displayed_selection) == 2:
            info = ""
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
            info += f"<p>Distance: {dist:.3f} ({print_pos(distv)})</p><p>Geometric center: ({geom_center})</p>"
            return info_selected_atoms + info

        info_natoms_geo_center = f"<p>{len(self.displayed_selection)} atoms selected</p><p>Geometric center: ({geom_center})</p>"

        # Report angle geometric center and normal.
        if len(self.displayed_selection) == 3:
            angle = self.displayed_structure.get_angle(*self.displayed_selection)
            normal = np.cross(
                *self.displayed_structure.get_distances(
                    self.displayed_selection[1],
                    [self.displayed_selection[0], self.displayed_selection[2]],
                    mic=False,
                    vector=True,
                )
            )
            normal = normal / np.linalg.norm(normal)
            return (
                info_selected_atoms
                + f"<p>{info_natoms_geo_center}</p><p>Angle: {angle: .3f}</p><p>Normal: ({print_pos(normal)})</p>"
            )

        # Report dihedral angle and geometric center.
        if len(self.displayed_selection) == 4:
            try:
                dihedral = self.displayed_structure.get_dihedral(
                    *self.displayed_selection
                )
                dihedral_str = f"{dihedral:.3f}"
            except ZeroDivisionError:
                dihedral_str = "nan"
            return (
                info_selected_atoms
                + f"<p>{info_natoms_geo_center}</p><p>Dihedral angle: {dihedral_str}</p>"
            )

        return info_selected_atoms + info_natoms_geo_center

    @tl.observe("displayed_selection")
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
            f"""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{self.files.value}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """
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
        report = cmdline.utils.common.get_workchain_report(
            self.process, "REPORT", max_depth=1
        )
        # Filter out the first column with dates
        filtered_report = re.sub(
            r"^[0-9]{4}.*\| ([A-Z]+)\]", r"\1", report, flags=re.MULTILINE
        )
        header = f"""
            Process {process.process_label},
            State: {tools.query.formatting.format_process_state(process.process_state.value)},
            UUID: {process.uuid} (pk: {process.pk})<br>
            Started {tools.query.formatting.format_relative_time(process.ctime)},
            Last modified {tools.query.formatting.format_relative_time(process.mtime)}<br>
        """
        self.value = f"{header}<pre>{filtered_report}</pre>"

        super().__init__(**kwargs)
