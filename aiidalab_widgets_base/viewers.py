from __future__ import annotations

"""Jupyter viewers for AiiDA data objects."""

import base64
import copy
import re
import warnings

import ase
import ipywidgets as ipw
import nglview
import numpy as np
import shortuuid
import spglib
import traitlets as tl
import vapory
from aiida import cmdline, orm, tools
from ase.data import colors
from IPython.display import clear_output, display
from matplotlib.colors import to_rgb

from .dicts import RGB_COLORS, Colors, Radius
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

    _viewer = AIIDA_VIEWER_MAPPING.get(obj.node_type)
    if isinstance(obj, orm.ProcessNode):
        # Allow to register specific viewers based on obj.process_type
        _viewer = AIIDA_VIEWER_MAPPING.get(obj.process_type, _viewer)

    if _viewer:
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
            sorted(parameter.get_dict().items()),
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


class NglViewerRepresentation(ipw.HBox):
    """This class represents the parameters for displaying a structure in NGLViewer.

    It is utilized in the structure viewer, where multiple representations can be defined,
    each specifying how to visually represent a particular subset of atoms.
    """

    viewer_class = None  # The structure viewer class that contains this representation.

    def __init__(self, style_id, indices=None, deletable=True, atom_show_threshold=1):
        """Initialize the representation.

        style_id: str
            Unique identifier for the representation.
        indices: list
            List of indices to be displayed.
        deletable: bool
            If True, add a button to delete the representation.
        atom_show_threshold: int
            only show the atom if the corresponding value in the representation array is larger or equal than this threshold.
        """

        self.atom_show_threshold = atom_show_threshold
        self.style_id = style_id

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
        self.viewer_class.delete_representation(self)

    def sync_myself_to_array_from_atoms_object(self, structure: ase.Atoms | None):
        """Update representation from the structure object."""
        if structure:
            if self.style_id in structure.arrays:
                self.selection.value = list_to_string_range(
                    np.where(self.atoms_in_representation(structure))[0], shift=1
                )

    def add_myself_to_atoms_object(self, structure: ase.Atoms | None):
        """Add representation array to the structure object. If the array already exists, update it."""
        if structure:
            array_representation = np.full(len(structure), -1, dtype=int)
            selection = np.array(
                string_range_to_list(self.selection.value, shift=-1)[0], dtype=int
            )
            # Only attempt to display the existing atoms.
            array_representation[selection[selection < len(structure)]] = 1
            structure.set_array(self.style_id, array_representation)

    def atoms_in_representation(self, structure: ase.Atoms | None = None):
        """Return an array of booleans indicating which atoms are present in the representation."""
        if structure and self.style_id in structure.arrays:
            return structure.arrays[self.style_id] >= self.atom_show_threshold
        natoms = 0 if not structure else len(structure)
        return np.zeros(natoms, dtype=bool)

    def nglview_parameters(self, indices):
        """Return the parameters dictionary of a representation."""
        nglview_parameters_dict = {
            "type": "spacefill",
            "params": {
                "sele": "@" + ",".join(map(str, indices))
                if len(indices) > 0
                else "none",
                "opacity": 1,
                "color": self.color.value,
            },
        }
        if self.type.value == "ball+stick":
            nglview_parameters_dict["params"]["radiusScale"] = self.size.value * 0.08
        elif self.type.value == "spacefill":
            nglview_parameters_dict["params"]["radiusScale"] = self.size.value * 0.25

        return nglview_parameters_dict


class _StructureDataBaseViewer(ipw.VBox):
    """Base viewer class for AiiDA structure or trajectory objects.

    Traits:
        _all_representations: list, containing all the representations of the structure.
        input_selection: list used mostly by external tools to populate the selection field.
        selection: list of currently selected atoms.
        displayed_selection: list of currently displayed atoms in the displayed structure, which also includes super-cell.
        supercell: list of supercell dimensions.
        cell: ase.cell.Cell object.
    """

    _all_representations = tl.List()
    input_selection = tl.List(tl.Int(), allow_none=True)
    selection = tl.List(tl.Int())
    displayed_selection = tl.List(tl.Int())
    supercell = tl.List(tl.Int())
    cell = tl.Instance(ase.cell.Cell, allow_none=True)
    DEFAULT_SELECTION_OPACITY = 0.2
    DEFAULT_SELECTION_RADIUS = 6
    DEFAULT_SELECTION_COLOR = "green"
    REPRESENTATION_PREFIX = "_aiidalab_viewer_representation_"
    DEFAULT_REPRESENTATION = "_aiidalab_viewer_representation_default"

    def __init__(
        self,
        configure_view=True,
        configuration_tabs=None,
        default_camera="orthographic",
        **kwargs,
    ):
        """Initialize the viewer.

        :param configure_view: If True, add configuration tabs (deprecated).
        :param configuration_tabs: List of configuration tabs (default: ["Selection", "Appearance", "Cell", "Download"]).
        :param default_camera: default camera (orthographic|perspective), can be changed in the Appearance tab.
        """
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
            [
                ipw.HTML(
                    description="Super cell:", style={"description_width": "initial"}
                ),
                *_supercell,
            ]
        )

        # 2. Choose background color.
        background_color = ipw.ColorPicker(
            description="Background",
            style={"description_width": "initial"},
            layout={"width": "200px"},
        )
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
        center_button.on_click(lambda _: self._viewer.center())

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
        self._all_representations = [
            NglViewerRepresentation(
                style_id=self.DEFAULT_REPRESENTATION,
                deletable=False,
                atom_show_threshold=0,
            )
        ]

        representation_accordion = ipw.Accordion(
            children=[
                ipw.VBox(
                    [
                        self.representations_header,
                        self.representation_output,
                        self.atoms_not_represented,
                        ipw.HBox(
                            [apply_representations, add_new_representation_button]
                        ),
                    ]
                )
            ],
        )
        representation_accordion.set_title(0, "Representations")
        representation_accordion.selected_index = None

        return ipw.VBox(
            [
                supercell_selector,
                background_color,
                camera_type,
                center_button,
                representation_accordion,
            ]
        )

    def _add_representation(self, _=None, style_id=None, indices=None):
        """Add a representation to the list of representations."""
        self._all_representations = [
            *self._all_representations,
            NglViewerRepresentation(
                style_id=style_id or f"{self.REPRESENTATION_PREFIX}{shortuuid.uuid()}",
                indices=indices,
            ),
        ]
        self._apply_representations()

    def delete_representation(self, representation: NglViewerRepresentation):
        try:
            index = self._all_representations.index(representation)
        except ValueError:
            self.representation_add_message.message = f"""<span style="color:red">Error:</span> Rep. {representation} not found."""
            return

        self._all_representations = (
            self._all_representations[:index] + self._all_representations[index + 1 :]
        )

        if representation.style_id in self.structure.arrays:
            del self.structure.arrays[representation.style_id]
        del representation
        self._apply_representations()

    @tl.observe("_all_representations")
    def _observe_all_representations(self, change):
        """Update the list of representations."""
        self.representation_output.children = change["new"]
        if change["new"]:
            self._all_representations[-1].viewer_class = self

    def _povray_cylinder(self, v1, v2, radius, color):
        """Create a cylinder for POVRAY."""
        return vapory.Cylinder(
            v1,
            v2,
            radius,
            vapory.Pigment("color", color),
            vapory.Finish("phong", 0.8, "reflection", 0.05),
        )

    def _cylinder(self, v1, v2, radius, color):
        """Create a cylinder for NGLViewer."""
        return (
            "cylinder",
            tuple(v1),
            tuple(v2),
            tuple(color),
            radius,
        )

    def _compute_bonds(self, structure, radius=1.0, color="element", povray=False):
        """Create an list of bonds for the structure."""

        import ase.neighborlist

        bonds = []
        if len(structure) <= 1:
            return []
        # The radius is scaled by 0.04 to have a better visual appearance.
        radius = radius * 0.04

        # The value 1.09 is chosen based on our experience. It is a good compromise between showing too many bonds
        # and not showing bonds that should be there.
        cutoff = ase.neighborlist.natural_cutoffs(structure, mult=1.09)

        ii, bond_vectors = ase.neighborlist.neighbor_list(
            "iD", structure, cutoff, self_interaction=False
        )
        nb = len(ii)
        # bond start position
        v1 = structure.positions[ii]
        # middle position
        v2 = v1 + bond_vectors * 0.5

        # Choose the correct way for computing the cylinder.
        if povray:
            symbols = structure.get_chemical_symbols()
            bonds = [
                self._povray_cylinder(v1[ib], v2[ib], radius, Colors[symbols[ii[ib]]])
                for ib in range(nb)
            ]
        else:
            if color == "element":
                numbers = structure.get_atomic_numbers()
                bonds = [
                    self._cylinder(
                        v1[ib], v2[ib], radius, colors.jmol_colors[numbers[ii[ib]]]
                    )
                    for ib in range(nb)
                ]
            else:
                bonds = [
                    self._cylinder(v1[ib], v2[ib], radius, RGB_COLORS[color])
                    for ib in range(nb)
                ]
        return bonds

    def _apply_representations(self, change=None):
        """Apply the representations to the displayed structure."""
        representation_ids = []

        # Representation can only be applied if a structure is present.
        if self.structure is None:
            return

        # Add existing representations to the structure.
        for representation in self._all_representations:
            representation.add_myself_to_atoms_object(self.structure)
            representation_ids.append(representation.style_id)

        # Remove missing representations from the structure.
        for array in self.structure.arrays:
            if (
                array.startswith(self.REPRESENTATION_PREFIX)
                and array not in representation_ids
            ):
                del self.structure.arrays[array]
        self._observe_structure({"new": self.structure})
        self._check_missing_atoms_in_representations()

    def _check_missing_atoms_in_representations(self):
        missing_atoms = np.zeros(self.natoms)
        for rep in self._all_representations:
            missing_atoms += rep.atoms_in_representation(self.structure)
        missing_atoms = np.where(missing_atoms == 0)[0]
        if len(missing_atoms) > 0:
            self.atoms_not_represented.value = (
                "Atoms excluded from representations: "
                + list_to_string_range(list(missing_atoms), shift=1)
            )
        else:
            self.atoms_not_represented.value = ""

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

            self.cell_a_length.value = (
                f"|<i><b>a</b></i>|: {self.cell.lengths()[0]:.4f}"
            )
            self.cell_b_length.value = (
                f"|<i><b>b</b></i>|: {self.cell.lengths()[1]:.4f}"
            )
            self.cell_c_length.value = (
                f"|<i><b>c</b></i>|: {self.cell.lengths()[2]:.4f}"
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

        bonds = self._compute_bonds(bb, povray=True)

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

        objects = [
            light,
            *spheres,
            *edges,
            *bonds,
            vapory.Background("color", np.array(to_rgb(self._viewer.background))),
        ]

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

    def highlight_atoms(
        self,
        list_of_atoms,
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
                list_of_atoms,
                np.where(
                    representation.atoms_in_representation(self.displayed_structure)
                )[0],
            )
            if len(indices) > 0:
                params = representation.nglview_parameters(indices)
                params["params"]["name"] = f"highlight_representation_{i}"
                params["params"]["opacity"] = 0.8
                params["params"]["color"] = "darkgreen"
                params["params"]["component_index"] = 0

                # Use directly the remote call for more flexibility.
                self._viewer._remote_call(
                    "addRepresentation",
                    target="compList",
                    args=[params["type"]],
                    kwargs=params["params"],
                )

    def remove_viewer_components(self, c=None):
        """Remove all components from the viewer except the one specified."""
        if hasattr(self._viewer, "component_0"):
            self._viewer.component_0.clear_representations()
            cid = self._viewer.component_0.id
            self._viewer.remove_component(cid)

    @tl.default("supercell")
    def _default_supercell(self):
        return [1, 1, 1]

    @tl.observe("input_selection")
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

    @tl.observe("displayed_selection")
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

    def download(self, _=None):
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
        self.structure.write(tmp.name, format=file_format)
        with open(tmp.name, "rb") as raw:
            return base64.b64encode(raw.read()).decode()

    @property
    def thumbnail(self):
        return self._prepare_payload(file_format="png")

    @property
    def natoms(self):
        """Number of atoms in the structure."""
        return 0 if self.structure is None else len(self.structure)


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
        [
            tl.Instance(ase.Atoms),
            tl.Instance(orm.StructureData),
            tl.Instance(orm.CifData),
        ],
        allow_none=True,
    )
    displayed_structure = tl.Instance(ase.Atoms, allow_none=True, read_only=True)
    pk = tl.Int(allow_none=True)

    def __init__(self, structure=None, **kwargs):
        super().__init__(**kwargs)
        self.structure = structure

    @tl.observe("supercell")
    def _observe_supercell(self, _=None):
        if self.structure is not None:
            self.set_trait(
                "displayed_structure", None
            )  # To make sure the structure is always updated.
            # nglview displays structures by first saving them to a temporary "pdb" file, which necessitates
            # converting the unit cell and atomic positions into a standard form where the a-axis aligns along the x-axis.
            # This transformation can cause discrepancies between the atom positions and custom bonds calculated from the original structure.
            # To mitigate this, we transform the "displayed_structure" into the standard form prior to rendering in nglview.
            # This ensures that nglview's internal handling does not further modify the structure unexpectedly.
            standard_structure = self.structure.copy()
            standard_structure.set_cell(
                self.structure.cell.standard_form()[0], scale_atoms=True
            )
            self.set_trait(
                "displayed_structure", standard_structure.repeat(self.supercell)
            )

    @tl.validate("structure")
    def _valid_structure(self, change):
        """Update structure."""
        structure = change["value"]
        if isinstance(structure, ase.Atoms):
            self.pk = None
        elif isinstance(structure, (orm.StructureData, orm.CifData)):
            self.pk = structure.pk
            structure = structure.get_ase()

        # Add default representation array if it is not present.
        # This will make sure that the new structure is displayed at the beginning.
        if self.DEFAULT_REPRESENTATION not in structure.arrays:
            structure.set_array(
                self.DEFAULT_REPRESENTATION,
                np.zeros(len(structure), dtype=int),
            )
        return structure  # This also includes the case when the structure is None.

    @tl.observe("structure")
    def _observe_structure(self, change=None):
        """Update displayed_structure trait after the structure trait has been modified."""
        structure = change["new"]

        self._viewer.clear_representations(component=0)

        if not structure:
            self.set_trait("displayed_structure", None)
            self.set_trait("cell", None)
            return

        # Make sure that the representation arrays from structure are present in the viewer.
        structure_ids = [
            style_id
            for style_id in structure.arrays
            if style_id.startswith(self.REPRESENTATION_PREFIX)
        ]
        representation_ids = [rep.style_id for rep in self._all_representations]

        for style_id in structure_ids:
            try:
                index = representation_ids.index(style_id)
                self._all_representations[index].sync_myself_to_array_from_atoms_object(
                    structure
                )
            except ValueError:
                self._add_representation(
                    style_id=style_id,
                    indices=np.where(structure.arrays[self.style_id] >= 1)[0],
                )
        # Empty atoms selection for the representations that are not present in the structure.
        # Typically this happens when a new structure is imported.
        for i, style_id in enumerate(representation_ids):
            if style_id not in structure_ids:
                self._all_representations[i].selection.value = ""

        self._observe_supercell()  # To trigger an update of the displayed structure
        self.set_trait("cell", structure.cell)

    @tl.observe("displayed_structure")
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
                bonds = []
                nglview_params = []
                for representation in self._all_representations:
                    if representation.show.value:
                        indices = np.where(
                            representation.atoms_in_representation(
                                self.displayed_structure
                            )
                        )[0]
                        nglview_params.append(
                            representation.nglview_parameters(indices)
                        )

                        # Add bonds if ball+stick representation is used.
                        if representation.type.value == "ball+stick":
                            bonds += self._compute_bonds(
                                self.displayed_structure[indices],
                                representation.size.value,
                                representation.color.value,
                            )
                self._viewer.set_representations(nglview_params, component=0)
                self._viewer.add_unitcell()
                self._viewer._add_shape(set(bonds), name="bonds")
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
                dihedral_str = f"{dihedral:.3f}"
            except ZeroDivisionError:
                dihedral_str = "nan"
            info += f"<p>Dihedral angle: {dihedral_str}</p>"

        return (
            info
            + f"<p>Geometric center: ({geom_center})</p>"
            + f"<p>{len(self.displayed_selection)} atoms selected</p>"
        )

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

    def change_file_view(self, _=None):
        try:
            with self._folder.base.repository.open(self.files.value) as fobj:
                self.text.value = fobj.read()
        except UnicodeDecodeError:
            self.text.value = "[Binary file, preview not available]"

    def download(self, _=None):
        """Download selected file."""
        from IPython.display import Javascript

        # TODO: Preparing large files for download might take a while.
        # Can we do a streaming solution?
        raw_bytes = self._folder.get_object_content(self.files.value, "rb")
        base64_payload = base64.b64encode(raw_bytes).decode()

        javas = Javascript(
            f"""
            var link = document.createElement('a');
            link.href = "data:;base64,{base64_payload}"
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
            plot_info = bands._get_bandplot_data(cartesian=True, join_symbol="|")
            # Extract relevant data
            y_data = plot_info["y"].transpose().tolist()
            x_data = [plot_info["x"] for i in range(len(y_data))]
            labels = plot_info["labels"]
            # Create the figure
            plot = figure(y_axis_label=f"Dispersion ({bands.units})")
            plot.multi_line(x_data, y_data, line_width=2, line_color="red")
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
