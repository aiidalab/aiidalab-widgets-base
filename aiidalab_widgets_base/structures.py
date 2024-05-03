"""Module to provide functionality to import structures."""

import datetime
import functools
import io
import pathlib
import tempfile

import ase
import ipywidgets as ipw
import numpy as np
import spglib
import traitlets as tl
from aiida import engine, orm, plugins

# Local imports
from .data import FunctionalGroupSelectorWidget
from .utils import StatusHTML, exceptions, get_ase_from_file, get_formula
from .viewers import StructureDataViewer

CifData = plugins.DataFactory("core.cif")
StructureData = plugins.DataFactory("core.structure")
TrajectoryData = plugins.DataFactory("core.array.trajectory")

SYMBOL_RADIUS = {
    key: ase.data.covalent_radii[i] for i, key in enumerate(ase.data.chemical_symbols)
}


class StructureManagerWidget(ipw.VBox):
    """Upload a structure and store it in AiiDA database.

    Attributes:
        structure(Atoms): trait that contains the selected structure. 'None' if no structure is selected.
        structure_node(StructureData, CifData): trait that contains AiiDA structure object
        node_class(str): trait that contains structure_node type (as string).
    """

    input_structure = tl.Union(
        [tl.Instance(ase.Atoms), tl.Instance(orm.Data)], allow_none=True
    )
    structure = tl.Instance(ase.Atoms, allow_none=True)
    structure_node = tl.Instance(orm.Data, allow_none=True, read_only=True)
    node_class = tl.Unicode()

    SUPPORTED_DATA_FORMATS = {"CifData": "core.cif", "StructureData": "core.structure"}

    def __init__(
        self,
        importers,
        viewer=None,
        editors=None,
        storable=True,
        node_class=None,
        **kwargs,
    ):
        """
        Arguments:
            importers(list): list of tuples each containing the displayed name of importer and the
                importer object. Each object should contain 'structure' trait pointing to the imported
                structure. The trait will be linked to 'structure' trait of this class.

            storable(bool): Whether to provide Store button (together with Store format)

            node_class(str): AiiDA node class for storing the structure.
                Possible values: 'StructureData', 'CifData' or None (let the user decide).
                Note: If your workflows require a specific node class, better fix it here.
        """

        # History of modifications
        self.history = []

        # Undo functionality.
        btn_undo = ipw.Button(description="Undo", button_style="success")
        btn_undo.on_click(self.undo)
        self.structure_set_by_undo = False

        # To keep track of last inserted structure object
        self._inserted_structure = None

        # Structure viewer.
        if viewer:
            self.viewer = viewer
        else:
            self.viewer = StructureDataViewer()
        tl.dlink((self, "structure"), (self.viewer, "structure"))

        # Store button.
        self.btn_store = ipw.Button(description="Store in AiiDA", disabled=True)
        self.btn_store.on_click(self.store_structure)

        # Label and description that are stored along with the new structure.
        self.structure_label = ipw.Text(description="Label")
        self.structure_description = ipw.Text(description="Description")

        # Store format selector.
        data_format = ipw.RadioButtons(
            options=tuple(
                (key, value) for key, value in self.SUPPORTED_DATA_FORMATS.items()
            ),
            description="Data type:",
        )
        tl.link((data_format, "label"), (self, "node_class"))

        # Store button, store class selector, description.
        store_and_description = [self.btn_store] if storable else []

        if node_class is None:
            store_and_description.append(data_format)
        elif node_class in self.SUPPORTED_DATA_FORMATS:
            self.node_class = node_class
        else:
            raise ValueError(
                f"Unknown data format '{node_class}'. Options: {list(self.SUPPORTED_DATA_FORMATS.keys())}"
            )
        self.output = ipw.HTML("")

        children = [
            self._structure_importers(importers),
            self.viewer,
            ipw.HBox(
                [
                    *store_and_description,
                    self.structure_label,
                    self.structure_description,
                ]
            ),
        ]

        structure_editors = self._structure_editors(editors)
        if structure_editors:
            structure_editors = ipw.VBox([btn_undo, structure_editors])
            accordion = ipw.Accordion([structure_editors])
            accordion.selected_index = None
            accordion.set_title(0, "Edit Structure")
            children += [accordion]

        super().__init__(children=[*children, self.output], **kwargs)

    def _structure_importers(self, importers):
        """Preparing structure importers."""
        if not isinstance(importers, (list, tuple)):
            raise exceptions.ListOrTuppleError(importers)

        # If there is only one importer - no need to make tabs.
        if len(importers) == 1:
            # Assigning a function which will be called when importer provides a structure.
            tl.dlink((importers[0], "structure"), (self, "input_structure"))
            return importers[0]

        # Otherwise making one tab per importer.
        importers_tab = ipw.Tab()
        importers_tab.children = list(importers)  # One importer per tab.
        for i, importer in enumerate(importers):
            # Labeling tabs.
            importers_tab.set_title(i, importer.title)
            tl.dlink((importer, "structure"), (self, "input_structure"))
        return importers_tab

    def _structure_editors(self, editors):
        """Preparing structure editors."""
        if editors and len(editors) == 1:
            tl.link((editors[0], "structure"), (self, "structure"))

            if editors[0].has_trait("input_selection"):
                tl.dlink(
                    (editors[0], "input_selection"), (self.viewer, "input_selection")
                )

            if editors[0].has_trait("selection"):
                tl.dlink((self.viewer, "selection"), (editors[0], "selection"))

            if editors[0].has_trait("camera_orientation"):
                tl.dlink(
                    (self.viewer._viewer, "_camera_orientation"),
                    (editors[0], "camera_orientation"),
                )

            return editors[0]

        # If more than one editor was defined.
        if editors:
            editors_tab = ipw.Tab()
            editors_tab.children = tuple(editors)
            for i, editor in enumerate(editors):
                editors_tab.set_title(i, editor.title)
                tl.link((editor, "structure"), (self, "structure"))
                if editor.has_trait("input_selection"):
                    tl.dlink(
                        (editor, "input_selection"), (self.viewer, "input_selection")
                    )
                if editor.has_trait("selection"):
                    tl.link((editor, "selection"), (self.viewer, "selection"))
                if editor.has_trait("camera_orientation"):
                    tl.dlink(
                        (self.viewer._viewer, "_camera_orientation"),
                        (editor, "camera_orientation"),
                    )
            return editors_tab
        return None

    def store_structure(self, _=None):
        """Stores the structure in AiiDA database."""

        if self.structure_node is None:
            return
        if self.structure_node.is_stored:
            self.output.value = (
                f"Already stored in AiiDA [{self.structure_node}], skipping..."
            )
            return
        self.btn_store.disabled = True
        self.structure_node.label = self.structure_label.value
        self.structure_label.disabled = True
        self.structure_node.description = self.structure_description.value
        self.structure_description.disabled = True

        if (
            isinstance(self.input_structure, orm.Data)
            and self.input_structure.is_stored
        ):
            # Make a link between self.input_structure and self.structure_node
            @engine.calcfunction
            def user_modifications(source_structure):  # noqa F841
                return self.structure_node

            structure_node = user_modifications(self.input_structure)

        else:
            structure_node = self.structure_node.store()
        self.output.value = f"Stored in AiiDA [{structure_node}]"

    def undo(self, _=None):
        """Undo modifications."""
        self.structure_set_by_undo = True
        if self.history:
            self.history = self.history[:-1]
            if self.history:
                self.structure = self.history[-1]
            else:
                self.input_structure = None
        self.structure_set_by_undo = False

    @staticmethod
    @tl.default("node_class")
    def _default_node_class():
        return "StructureData"

    @tl.observe("node_class")
    def _change_structure_node(self, _=None):
        with self.hold_trait_notifications():
            self._sync_structure_node()

    def _sync_structure_node(self):
        """Synchronize the structure_node trait using the currently provided info."""
        if len(self.history) > 1:
            # There are some modifications, so converting from ASE.
            structure_node = self._convert_to_structure_node(self.structure)
        else:
            structure_node = self._convert_to_structure_node(self.input_structure)
        self.set_trait("structure_node", structure_node)

    def _convert_to_structure_node(self, structure):
        """Convert structure of any type to the StructureNode object."""
        if structure is None:
            return None
        structure_node_type = plugins.DataFactory(
            self.SUPPORTED_DATA_FORMATS[self.node_class]
        )

        # If the input_structure trait is set to Atoms object, structure node must be created from it.
        if isinstance(structure, ase.Atoms):
            # If the Atoms object was created by SmilesWidget,
            # attach its SMILES code as an extra.
            structure_node = structure_node_type(ase=structure)
            if "smiles" in structure.info:
                structure_node.base.extras.set("smiles", structure.info["smiles"])
            return structure_node

        # If the input_structure trait is set to AiiDA node, check what type
        if isinstance(structure, orm.Data):
            # Transform the structure to the structure_node_type if needed.
            if isinstance(structure, structure_node_type):
                return structure

        # Using self.structure, as it was already converted to the ASE Atoms object.
        return structure_node_type(ase=self.structure)

    @tl.observe("structure_node")
    def _observe_structure_node(self, change):
        """Modify structure label and description when a new structure is provided."""
        struct = change["new"]
        if struct is None:
            self.btn_store.disabled = True
            self.structure_label.value = ""
            self.structure_label.disabled = True
            self.structure_description.value = ""
            self.structure_description.disabled = True
            return
        if struct.is_stored:
            self.btn_store.disabled = True
            self.structure_label.value = struct.label
            self.structure_label.disabled = True
            self.structure_description.value = struct.description
            self.structure_description.disabled = True
        else:
            self.btn_store.disabled = False
            self.structure_label.value = self.structure.get_chemical_formula()
            self.structure_label.disabled = False
            self.structure_description.value = ""
            self.structure_description.disabled = False

    @tl.observe("input_structure")
    def _observe_input_structure(self, change):
        """Returns ASE atoms object and sets structure_node trait."""
        # If the `input_structure` trait is set to Atoms object, then the `structure` trait should be set to it as well.
        self.history = []

        if isinstance(change["new"], ase.Atoms):
            self.structure = change["new"]

        # If the `input_structure` trait is set to AiiDA node, then the `structure` trait should
        # be converted to an ASE Atoms object.
        elif isinstance(
            change["new"], CifData
        ):  # Special treatement of the CifData object
            str_io = io.StringIO(change["new"].get_content())
            self.structure = ase.io.read(
                str_io, format="cif", reader="ase", store_tags=True
            )
        elif isinstance(change["new"], StructureData):
            self.structure = change["new"].get_ase()

        else:
            self.structure = None

    @tl.observe("structure")
    def _structure_changed(self, change=None):
        """Perform some operations that depend on the value of `structure` trait.

        This function enables/disables `btn_store` widget if structure is provided/set to None.
        Also, the function sets `structure_node` trait to the selected node type.
        """

        if not self.structure_set_by_undo:
            self.history.append(change["new"])

        # If structure trait was set to None, structure_node should become None as well.
        if self.structure is None:
            self.set_trait("structure_node", None)
            self.btn_store.disabled = True
            return

        self.btn_store.disabled = False
        with self.hold_trait_notifications():
            self._sync_structure_node()


class StructureUploadWidget(ipw.VBox):
    """Class that allows to upload structures from user's computer."""

    structure = tl.Union(
        [tl.Instance(ase.Atoms), tl.Instance(orm.Data)], allow_none=True
    )

    def __init__(
        self, title="", description="Upload Structure", allow_trajectories=False
    ):
        self.title = title
        self.file_upload = ipw.FileUpload(
            description=description, multiple=False, layout={"width": "initial"}
        )
        # Whether to allow uploading multiple structures from a single file.
        # In this case, we create TrajectoryData node.
        self.allow_trajectories = allow_trajectories
        supported_formats = ipw.HTML(
            """<a href="https://wiki.fysik.dtu.dk/ase/ase/io/io.html#ase.io.write" target="_blank">
        Supported structure formats
        </a>"""
        )
        self._status_message = StatusHTML(clear_after=5)
        self.file_upload.observe(self._on_file_upload, names="value")
        super().__init__(
            children=[self.file_upload, supported_formats, self._status_message]
        )

    def _validate_and_fix_ase_cell(self, ase_structure, vacuum_ang=10.0):
        """
        Checks if the ase Atoms object has a cell set,
        otherwise sets it to bounding box plus specified "vacuum" space
        """
        if not ase_structure:
            return None

        cell = ase_structure.cell

        # TODO: Since AiiDA 2.0, zero cell is possible if PBC=false
        # so we should honor that here and do not put artificial cell
        # around gas phase molecules.
        if (
            np.linalg.norm(cell[0]) < 0.1
            or np.linalg.norm(cell[1]) < 0.1
            or np.linalg.norm(cell[2]) < 0.1
        ):
            # if any of the cell vectors is too short, consider it faulty
            # set cell as bounding box + vacuum_ang
            bbox = np.ptp(ase_structure.positions, axis=0)
            new_structure = ase_structure.copy()
            new_structure.cell = bbox + vacuum_ang
            return new_structure
        return ase_structure

    def _on_file_upload(self, change=None):
        """When file upload button is pressed."""
        for fname, item in change["new"].items():
            self.structure = self._read_structure(fname, item["content"])
            self.file_upload.value.clear()
            break

    def _read_structure(self, fname, content):
        suffix = "".join(pathlib.Path(fname).suffixes)
        if suffix == ".cif":
            try:
                return CifData(file=io.BytesIO(content))
            except Exception as e:
                self._status_message.message = f"""
                    <div class="alert alert-warning">Could not parse CIF file {fname}: {e}
                    Trying ASE reader...</div>
                    """

        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            try:
                if suffix == ".cif":
                    structures = get_ase_from_file(temp_file.name, format="cif")
                else:
                    structures = get_ase_from_file(temp_file.name)
            except ValueError as e:
                self._status_message.message = f"""
                    <div class="alert alert-danger">ERROR: {e}</div>
                    """
                return None
            except KeyError:
                self._status_message.message = f"""
                    <div class="alert alert-danger">ERROR: Could not parse file {fname}</div>
                    """
                return None

            if len(structures) > 1:
                if self.allow_trajectories:
                    return TrajectoryData(
                        structurelist=[
                            StructureData(
                                ase=self._validate_and_fix_ase_cell(ase_struct)
                            )
                            for ase_struct in structures
                        ]
                    )
                else:
                    self._status_message.message = f"""
                        <div class="alert alert-danger">ERROR: More than one structure found in file {fname}</div>
                        """
                    return None

            return self._validate_and_fix_ase_cell(structures[0])


class StructureExamplesWidget(ipw.VBox):
    """Class to provide example structures for selection."""

    structure = tl.Instance(ase.Atoms, allow_none=True)

    def __init__(self, examples, title="", **kwargs):
        self.title = title
        self.on_structure_selection = lambda _structure_ase, _name: None
        self._select_structure = ipw.Dropdown(
            options=self.get_example_structures(examples)
        )
        self._select_structure.observe(self._on_select_structure, names=["value"])
        super().__init__(children=[self._select_structure], **kwargs)

    @staticmethod
    def get_example_structures(examples):
        """Get the list of example structures."""
        if not isinstance(examples, list):
            raise TypeError(
                f"parameter examples should be of type list, {type(examples)} given"
            )
        return [("Select structure", False), *examples]

    def _on_select_structure(self, change=None):
        """When structure is selected."""

        self.structure = (
            get_ase_from_file(self._select_structure.value)[0]
            if self._select_structure.value
            else None
        )

    @tl.default("structure")
    def _default_structure(self):
        return None


class StructureBrowserWidget(ipw.VBox):
    """Class to query for structures stored in the AiiDA database.

    :param title: Title of the widget displayed on a tab in StructureManagerWidget
    :type title: string
    :param query_types: A tuple of Data node types that are searched (default: StructureData, CifData)
    :type query_types: tuple
    """

    structure = tl.Union(
        [tl.Instance(ase.Atoms), tl.Instance(orm.Data)], allow_none=True
    )

    def __init__(self, title="", query_types=None):
        self.title = title

        # Structure objects we want to query for.
        if query_types:
            self.query_structure_type = query_types
        else:
            self.query_structure_type = (StructureData, CifData)

        # Extracting available process labels.
        qbuilder = orm.QueryBuilder().append(
            (orm.CalcJobNode, orm.WorkChainNode), project="label"
        )
        self.drop_label = ipw.Dropdown(
            options=sorted({"All"}.union({i[0] for i in qbuilder.iterall() if i[0]})),
            value="All",
            description="Process Label",
            disabled=True,
            style={"description_width": "120px"},
            layout={"width": "50%"},
        )
        self.drop_label.observe(self.search, names="value")

        # Disable process labels selection if we are not looking for the calculated structures.
        def disable_drop_label(change):
            self.drop_label.disabled = not change["new"] == "calculated"

        # Select structures kind.
        self.mode = ipw.RadioButtons(
            options=["all", "uploaded", "edited", "calculated"], layout={"width": "25%"}
        )
        self.mode.observe(self.search, names="value")
        self.mode.observe(disable_drop_label, names="value")

        # Date range.
        # Note: there is Date picker widget, but it currently does not work in Safari:
        # https://ipywidgets.readthedocs.io/en/latest/examples/Widget%20List.html#Date-picker
        date_text = ipw.HTML(value="<p>Select the date range:</p>")
        self.start_date_widget = ipw.Text(
            value="", description="From: ", style={"description_width": "120px"}
        )
        self.end_date_widget = ipw.Text(value="", description="To: ")

        # Search button.
        btn_search = ipw.Button(
            description="Search",
            button_style="info",
            layout={"width": "initial", "margin": "2px 0 0 2em"},
        )
        btn_search.on_click(self.search)

        age_selection = ipw.VBox(
            [
                date_text,
                ipw.HBox([self.start_date_widget, self.end_date_widget, btn_search]),
            ],
            layout={"border": "1px solid #fafafa", "padding": "1em"},
        )

        h_line = ipw.HTML("<hr>")
        box = ipw.VBox([age_selection, h_line, ipw.HBox([self.mode, self.drop_label])])

        self.results = ipw.Dropdown(layout={"width": "900px"})
        self.results.observe(self._on_select_structure, names="value")
        self.search()
        super().__init__([box, h_line, self.results])

    def preprocess(self):
        """Search structures in AiiDA database and add formula extra to them."""

        queryb = orm.QueryBuilder()
        queryb.append(
            self.query_structure_type, filters={"extras": {"!has_key": "formula"}}
        )
        for item in queryb.all():  # iterall() would interfere with base.extras.set()
            try:
                formula = get_formula(item[0])
                item[0].base.extras.set("formula", formula)
            except ValueError:
                pass

    def search(self, _=None):
        """Launch the search of structures in AiiDA database."""
        self.preprocess()

        qbuild = orm.QueryBuilder()

        # If the date range is valid, use it for the search
        try:
            start_date = datetime.datetime.strptime(
                self.start_date_widget.value, "%Y-%m-%d"
            )
            end_date = datetime.datetime.strptime(
                self.end_date_widget.value, "%Y-%m-%d"
            ) + datetime.timedelta(hours=24)

        # Otherwise revert to the standard (i.e. last 7 days)
        except ValueError:
            start_date = datetime.datetime.now() - datetime.timedelta(days=7)
            end_date = datetime.datetime.now() + datetime.timedelta(hours=24)

            self.start_date_widget.value = start_date.strftime("%Y-%m-%d")
            self.end_date_widget.value = end_date.strftime("%Y-%m-%d")

        filters = {}
        filters["ctime"] = {"and": [{">": start_date}, {"<=": end_date}]}

        if self.mode.value == "uploaded":
            qbuild2 = (
                orm.QueryBuilder()
                .append(self.query_structure_type, project=["id"], tag="structures")
                .append(orm.Node, with_outgoing="structures")
            )
            processed_nodes = [n[0] for n in qbuild2.all()]
            if processed_nodes:
                filters["id"] = {"!in": processed_nodes}
            qbuild.append(self.query_structure_type, filters=filters)

        elif self.mode.value == "calculated":
            if self.drop_label.value == "All":
                qbuild.append(
                    (orm.CalcJobNode, orm.WorkChainNode), tag="calcjobworkchain"
                )
            else:
                qbuild.append(
                    (orm.CalcJobNode, orm.WorkChainNode),
                    filters={"label": self.drop_label.value},
                    tag="calcjobworkchain",
                )
            qbuild.append(
                self.query_structure_type,
                with_incoming="calcjobworkchain",
                filters=filters,
            )

        elif self.mode.value == "edited":
            qbuild.append(orm.CalcFunctionNode)
            qbuild.append(
                self.query_structure_type,
                with_incoming=orm.CalcFunctionNode,
                filters=filters,
            )

        elif self.mode.value == "all":
            qbuild.append(self.query_structure_type, filters=filters)

        qbuild.order_by({self.query_structure_type: {"ctime": "desc"}})
        matches = {n[0] for n in qbuild.iterall()}
        matches = sorted(matches, reverse=True, key=lambda n: n.ctime)

        options = [(f"Select a Structure ({len(matches)} found)", False)]
        for mch in matches:
            label = f"PK: {mch.pk}"
            label += " | " + mch.ctime.strftime("%Y-%m-%d %H:%M")
            label += " | " + mch.base.extras.get("formula", "")
            label += " | " + mch.node_type.split(".")[-2]
            label += " | " + mch.label
            label += " | " + mch.description
            options.append((label, mch))

        self.results.options = options

    def _on_select_structure(self, _=None):
        self.structure = self.results.value or None


class SmilesWidget(ipw.VBox):
    """Convert SMILES into 3D structure."""

    structure = tl.Instance(ase.Atoms, allow_none=True)

    SPINNER = """<i class="fa fa-spinner fa-pulse" style="color:red;" ></i>"""

    def __init__(self, title=""):
        self.title = title
        try:
            from rdkit import Chem  # noqa: F401
            from rdkit.Chem import AllChem  # noqa: F401
        except ImportError:
            super().__init__(
                [
                    ipw.HTML(
                        "The SmilesWidget requires the rdkit library, "
                        "but the library was not found."
                    )
                ]
            )
            return

        self.smiles = ipw.Text(placeholder="C=C")
        self.create_structure_btn = ipw.Button(
            description="Generate molecule",
            button_style="primary",
            tooltip="Generate molecule from SMILES string",
        )
        self.create_structure_btn.on_click(self._on_button_pressed)
        self.output = ipw.HTML("")

        super().__init__(
            [ipw.HBox([self.smiles, self.create_structure_btn]), self.output]
        )

    def _make_ase(self, species, positions, smiles):
        """Create ase Atoms object."""
        from sklearn.decomposition import PCA

        # Get the principal axes and realign the molecule along z-axis.
        if len(species) > 2:
            positions = PCA(n_components=3).fit_transform(positions)
        atoms = ase.Atoms(species, positions=positions, pbc=False)
        atoms.cell = np.ptp(atoms.positions, axis=0) + 10
        atoms.center()
        # We're attaching this info so that it
        # can be later stored as an extra on AiiDA Structure node.
        atoms.info["smiles"] = smiles

        return atoms

    def _rdkit_opt(self, smiles, steps):
        """Optimize a molecule using force field and rdkit (needed for complex SMILES)."""
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            # Something is seriously wrong with the SMILES code,
            # just return None and don't attempt anything else.
            self.output.value = "RDKit ERROR: Invalid SMILES string"
            return None
        mol = Chem.AddHs(mol)

        conf_id = AllChem.EmbedMolecule(mol, maxAttempts=20, randomSeed=42)
        if conf_id < 0:
            # Retry with different generation method that is supposed to be
            # more stable. Perhaps we should switch to it by default.
            # https://greglandrum.github.io/rdkit-blog/posts/2021-01-31-looking-at-random-coordinate-embedding.html#look-at-some-of-the-troublesome-structures
            # https://www.rdkit.org/docs/source/rdkit.Chem.rdDistGeom.html#rdkit.Chem.rdDistGeom.EmbedMolecule
            conf_id = AllChem.EmbedMolecule(
                mol, maxAttempts=20, useRandomCoords=True, randomSeed=422
            )
        if conf_id < 0:
            self.output.value = "RDKit ERROR: Could not generate conformer"
            return None
        if AllChem.UFFHasAllMoleculeParams(mol):
            AllChem.UFFOptimizeMolecule(mol, maxIters=steps)
        else:
            self.output.value = "RDKit WARNING: Missing UFF parameters"

        positions = mol.GetConformer().GetPositions()
        natoms = mol.GetNumAtoms()
        species = [mol.GetAtomWithIdx(j).GetSymbol() for j in range(natoms)]
        return self._make_ase(species, positions, smiles)

    def _mol_from_smiles(self, smiles, steps=1000):
        """Convert SMILES to ASE structure using RDKit"""
        try:
            canonical_smiles = self.canonicalize_smiles(smiles)
            ase = self._rdkit_opt(canonical_smiles, steps)
        except ValueError as e:
            self.output.value = str(e)
            return None
        else:
            if canonical_smiles != smiles:
                self.output.value = f"Canonical SMILES: {canonical_smiles}"
            return ase

    def _on_button_pressed(self, change=None):
        """Convert SMILES to ASE structure when button is pressed."""
        self.output.value = ""

        if not self.smiles.value:
            return
        spinner = f"Screening possible conformers {self.SPINNER}"  # font-size:20em;
        self.output.value = spinner

        self.structure = self._mol_from_smiles(self.smiles.value)
        # Don't overwrite possible error/warning messages
        if self.output.value == spinner:
            self.output.value = ""

    # https://en.wikipedia.org/wiki/Simplified_molecular-input_line-entry_system#Terminology
    @staticmethod
    def canonicalize_smiles(smiles: str) -> str:
        """Canonicalize the SMILES code.

        :raises ValueError: if SMILES is invalid or if canonicalization fails
        """
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles, sanitize=True)
        if mol is None:
            # Something is seriously wrong with the SMILES code
            msg = "Invalid SMILES string"
            raise ValueError(msg)

        canonical_smiles = Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)
        if not canonical_smiles:
            msg = "SMILES canonicalization failed"
            raise ValueError(msg)
        return canonical_smiles

    @tl.default("structure")
    def _default_structure(self):
        return None


def _register_structure(operator):
    """
    Decorator for methods that manipulate (operate on) the selected structure.

    Checks whether a structure and selection is set and ensures that the
    arguments for structure and selection are passed by copy rather than
    reference. A pop-up warning message is shown in case that neither a
    structure or selection are set.
    """

    @functools.wraps(operator)
    def inner(ref, *args, **kwargs):
        if not ref.structure:
            ref._status_message.message = """
            <div class="alert alert-info">
            <strong>Please choose a structure first.</strong>
            </div>
            """
        else:
            operator(
                ref,
                *args,
                **kwargs,
                atoms=ref.structure.copy(),
            )

    return inner


def _register_selection(operator):
    """
    Decorator for methods that manipulate (operate on) the selected structure.

    Checks whether a structure and selection is set and ensures that the
    arguments for structure and selection are passed by copy rather than
    reference. A pop-up warning message is shown in case that neither a
    structure or selection are set.
    """

    @functools.wraps(operator)
    def inner(ref, *args, **kwargs):
        if not ref.selection:
            ref._status_message.message = """
            <div class="alert alert-info">
            <strong>Please select atoms first.</strong>
            </div>
            """
        else:
            operator(
                ref,
                *args,
                **kwargs,
                selection=ref.selection.copy(),
            )

    return inner


class BasicCellEditor(ipw.VBox):
    """Widget that allows for the basic cell editing."""

    structure = tl.Instance(ase.Atoms, allow_none=True)

    def __init__(self, title="Cell transform"):
        self.title = title
        self._status_message = StatusHTML()

        # cell transfor opration widget
        primitive_cell = ipw.Button(
            description="Convert to primitive cell",
            layout={"width": "initial"},
        )
        primitive_cell.on_click(self._to_primitive_cell)

        conventional_cell = ipw.Button(
            description="Convert to conventional cell",
            layout={"width": "initial"},
        )
        conventional_cell.on_click(self._to_conventional_cell)
        cell_parameters = (
            self.structure.get_cell_lengths_and_angles()
            if self.structure
            else [1, 0, 0, 0, 0, 0]
        )
        self.cell_parameters = ipw.HBox(
            [
                ipw.VBox(
                    [
                        ipw.HTML(
                            description=["a(Å)", "b(Å)", "c(Å)", "α", "β", "γ"][i],
                            layout={"width": "30px"},
                        ),
                        ipw.FloatText(
                            value=cell_parameters[i], layout={"width": "100px"}
                        ),
                    ]
                )
                for i in range(6)
            ]
        )
        # cell transformation matrix (4x4)
        self.cell_transformation = ipw.VBox(
            [
                ipw.HBox(
                    [
                        ipw.IntText(value=1 if i == j else 0, layout={"width": "60px"})
                        for j in range(3)
                    ]
                    + [ipw.FloatText(value=0, layout={"width": "60px"})]
                )
                for i in range(3)
            ]
        )
        apply_cell_parameters_button = ipw.Button(description="Apply cell parameters")
        apply_cell_parameters_button.on_click(self._apply_cell_parameters)
        self.scale_atoms_position = ipw.Checkbox(
            description="Scale atoms position",
            value=False,
            indent=False,
        )
        apply_cell_transformation = ipw.Button(description="Apply transformation")
        apply_cell_transformation.on_click(self._apply_cell_transformation)
        reset_transformatioin_button = ipw.Button(
            description="Reset matrix",
        )
        reset_transformatioin_button.on_click(self._reset_cell_transformation_matrix)
        super().__init__(
            children=[
                ipw.HBox(
                    [
                        primitive_cell,
                        conventional_cell,
                    ],
                ),
                self._status_message,
                ipw.VBox(
                    [
                        ipw.HTML(
                            "<b>Cell parameters:</b>",
                            layout={"margin": "20px 0px 10px 0px"},
                        ),
                        self.cell_parameters,
                        ipw.HBox(
                            [
                                apply_cell_parameters_button,
                                self.scale_atoms_position,
                            ]
                        ),
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.VBox(
                    [
                        ipw.HTML(
                            "<b>Cell Transformation:</b>",
                            layout={"margin": "20px 0px 10px 0px"},
                        ),
                        self.cell_transformation,
                        ipw.HBox(
                            [apply_cell_transformation, reset_transformatioin_button]
                        ),
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
            ],
        )

    @_register_structure
    def _to_primitive_cell(self, _=None, atoms=None):
        atoms = self._to_standard_cell(atoms, to_primitive=True)

        self.structure = atoms

    @_register_structure
    def _to_conventional_cell(self, _=None, atoms=None):
        atoms = self._to_standard_cell(atoms, to_primitive=False)

        self.structure = atoms

    @staticmethod
    def _to_standard_cell(
        structure: ase.Atoms, to_primitive=False, no_idealize=False, symprec=1e-5
    ):
        """The `standardize_cell` method from spglib and apply to ase.Atoms"""
        lattice = structure.get_cell()
        positions = structure.get_scaled_positions()
        numbers = structure.get_atomic_numbers()

        cell = (lattice, positions, numbers)

        # operation
        lattice, positions, numbers = spglib.standardize_cell(
            cell, to_primitive=to_primitive, no_idealize=no_idealize, symprec=symprec
        )

        return ase.Atoms(
            cell=lattice,
            scaled_positions=positions,
            numbers=numbers,
            pbc=[True, True, True],
        )

    @tl.observe("structure")
    def _observe_structure(self, change):
        """Update cell after the structure has been modified."""
        if change["new"] is not None:
            cell_parameters = change["new"].cell.cellpar()
            for i in range(6):
                self.cell_parameters.children[i].children[1].value = round(
                    cell_parameters[i], 4
                )
        else:
            for i in range(6):
                self.cell_parameters.children[i].children[1].value = 0

    @_register_structure
    def _apply_cell_parameters(self, _=None, atoms=None):
        """Apply the cell parameters to the structure."""
        # only update structure when atoms is not None.
        cell_parameters = [
            self.cell_parameters.children[i].children[1].value for i in range(6)
        ]
        if atoms is not None:
            atoms.set_cell(
                ase.cell.Cell.fromcellpar(cell_parameters),
                scale_atoms=self.scale_atoms_position.value,
            )
            self.structure = atoms

    @_register_structure
    def _apply_cell_transformation(self, _=None, atoms=None):
        """Apply the transformation matrix to the structure."""
        from ase.build import make_supercell

        # only update structure when atoms is not None.
        if atoms is not None:
            mat = np.zeros((3, 3))
            translate = np.zeros(3)
            for i in range(3):
                translate[i] = self.cell_transformation.children[i].children[3].value
                for j in range(3):
                    mat[i][j] = self.cell_transformation.children[i].children[j].value
            # transformation matrix may not work due to singularity, or
            # the number of generated atoms is not correct
            try:
                atoms = make_supercell(atoms, mat)
            except Exception as e:
                self._status_message.message = f"""
            <div class="alert alert-info">
            <strong>The transformation matrix is wrong! {e}</strong>
            </div>
            """
                return
            # translate
            atoms.translate(-atoms.cell.array.dot(translate))
            self.structure = atoms

    @_register_structure
    def _reset_cell_transformation_matrix(self, _=None, atoms=None):
        """Reset the transformation matrix to identity matrix."""
        for i in range(3):
            for j in range(4):
                self.cell_transformation.children[i].children[j].value = 0
            self.cell_transformation.children[i].children[i].value = 1


class BasicStructureEditor(ipw.VBox):
    """
    Widget that allows for the basic structure (molecule and
    position of periodic structure in cell) editing."""

    structure = tl.Instance(ase.Atoms, allow_none=True)
    input_selection = tl.List(tl.Int(), allow_none=True)
    selection = tl.List(tl.Int())
    camera_orientation = tl.List()

    def __init__(self, title=""):
        self.title = title

        # Define action vector.
        self.axis_p1 = ipw.Text(
            description="Starting point", value="0 0 0", layout={"width": "initial"}
        )
        self.axis_p2 = ipw.Text(
            description="Ending point", value="0 0 1", layout={"width": "initial"}
        )
        btn_def_atom1 = ipw.Button(
            description="From selection", layout={"width": "initial"}
        )
        btn_def_atom1.on_click(self.def_axis_p1)
        btn_def_atom2 = ipw.Button(
            description="From selection", layout={"width": "initial"}
        )
        btn_def_atom2.on_click(self.def_axis_p2)
        btn_get_from_camera = ipw.Button(
            description="Perp. to screen",
            button_style="warning",
            layout={"width": "initial"},
        )
        btn_get_from_camera.on_click(self.def_perpendicular_to_screen)

        # Define action point.
        self.point = ipw.Text(
            description="Action point", value="0 0 0", layout={"width": "initial"}
        )
        btn_def_pnt = ipw.Button(
            description="From selection", layout={"width": "initial"}
        )
        btn_def_pnt.on_click(self.def_point)

        # Move atoms.
        btn_move_dr = ipw.Button(description="Move", layout={"width": "initial"})
        btn_move_dr.on_click(self.translate_dr)
        self.displacement = ipw.FloatText(
            description=r"Move along action vector by $\Delta=$ ",
            value=1,
            step=0.1,
            style={"description_width": "initial"},
            layout={"width": "initial"},
        )

        btn_move_dxyz = ipw.Button(
            description="Move by XYZ", layout={"width": "initial"}
        )
        btn_move_dxyz.on_click(self.translate_dxdydz)
        btn_move_to_xyz = ipw.Button(
            description="Move to XYZ", layout={"width": "initial"}
        )
        btn_move_to_xyz.on_click(self.translate_to_xyz)
        self.dxyz = ipw.Text(
            description="XYZ move:",
            value="0 0 0",
            style={"description_width": "initial"},
            layout={"width": "initial", "margin": "0px 0px 0px 20px"},
        )

        # Rotate atoms.
        btn_rotate = ipw.Button(description="Rotate", layout={"width": "10%"})
        btn_rotate.on_click(self.rotate)
        self.phi = ipw.FloatText(
            description="Rotate around the action vector which starts from the action point",
            value=0,
            step=5,
            style={"description_width": "initial"},
            layout={"width": "initial"},
        )

        # Mirror atoms.
        btn_mirror_perp = ipw.Button(description="Mirror", layout={"width": "10%"})
        btn_mirror_perp.on_click(self.mirror)
        btn_mirror_3p = ipw.Button(description="Mirror", layout={"width": "10%"})
        btn_mirror_3p.on_click(self.mirror_3p)

        # Rotate atoms while aligning action vector with XYZ vector.
        btn_align = ipw.Button(description="Align", layout={"width": "10%"})
        btn_align.on_click(self.align)

        # Atoms selection.
        self.element = ipw.Dropdown(
            description="Select element",
            options=ase.data.chemical_symbols[1:],
            value="H",
            style={"description_width": "initial"},
            layout={"width": "initial"},
        )

        def disable_element(_=None):
            if self.ligand.value == 0:
                self.element.disabled = False
            else:
                self.element.disabled = True

        # Ligand selection.
        self.ligand = FunctionalGroupSelectorWidget()
        self.ligand.observe(disable_element, names="value")

        # Add atom.
        btn_add = ipw.Button(description="Add to selected", layout={"width": "initial"})
        btn_add.on_click(self.add)
        self.bond_length = ipw.FloatText(
            description="Bond lenght.", value=1.0, layout={"width": "140px"}
        )
        use_covalent_radius = ipw.Checkbox(
            value=True,
            description="Use covalent radius",
            style={"description_width": "initial"},
        )
        tl.link((use_covalent_radius, "value"), (self.bond_length, "disabled"))

        # Copy atoms.
        btn_copy_sel = ipw.Button(
            description="Copy selected", layout={"width": "initial"}
        )
        btn_copy_sel.on_click(self.copy_sel)

        # Modify atom.
        btn_modify = ipw.Button(
            description="Modify selected",
            button_style="warning",
            layout={"width": "initial"},
        )
        btn_modify.on_click(self.mod_element)

        # Remove atom.
        btn_remove = ipw.Button(
            description="Remove selected",
            button_style="danger",
            layout={"width": "initial"},
        )
        btn_remove.on_click(self.remove)

        # Automatically clear selection after point definition
        self.autoclear_selection = ipw.Checkbox(
            description='Clear selection after pressing "From seletion"',
            value=True,
            style={"description_width": "initial"},
        )

        self._status_message = StatusHTML()

        super().__init__(
            children=[
                ipw.HTML(
                    "<b>Action vector and point:</b>",
                    layout={"margin": "20px 0px 10px 0px"},
                ),
                ipw.HBox(
                    [
                        self.axis_p1,
                        btn_def_atom1,
                        self.axis_p2,
                        btn_def_atom2,
                        btn_get_from_camera,
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HBox(
                    [self.point, btn_def_pnt, self.autoclear_selection],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HTML(
                    "<b>Move atom(s):</b>", layout={"margin": "20px 0px 10px 0px"}
                ),
                ipw.HBox(
                    [
                        self.displacement,
                        btn_move_dr,
                        self.dxyz,
                        btn_move_dxyz,
                        btn_move_to_xyz,
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HBox([self.phi, btn_rotate], layout={"margin": "0px 0px 0px 20px"}),
                ipw.HBox(
                    [
                        ipw.HTML(
                            "Mirror on the plane perpendicular to the action vector",
                            layout={"margin": "0px 0px 0px 0px"},
                        ),
                        btn_mirror_perp,
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HBox(
                    [
                        ipw.HTML(
                            "Mirror on the plane containing action vector and action point",
                            layout={"margin": "0px 0px 0px 0px"},
                        ),
                        btn_mirror_3p,
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HBox(
                    [
                        ipw.HTML(
                            "Rotate atoms while aligning the action vector with the XYZ vector",
                            layout={"margin": "0px 0px 0px 0px"},
                        ),
                        btn_align,
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HTML(
                    "<b>Modify atom(s):</v>", layout={"margin": "20px 0px 10px 0px"}
                ),
                ipw.HBox([btn_copy_sel], layout={"margin": "0px 0px 0px 20px"}),
                ipw.HBox(
                    [self.element, self.ligand], layout={"margin": "0px 0px 0px 20px"}
                ),
                ipw.HBox(
                    [
                        btn_modify,
                        btn_add,
                        self.bond_length,
                        use_covalent_radius,
                    ],
                    layout={"margin": "0px 0px 0px 20px"},
                ),
                ipw.HBox([btn_remove], layout={"margin": "0px 0px 0px 20px"}),
                self._status_message,
            ]
        )

    def str2vec(self, string):
        return np.array(list(map(float, string.split())))

    def vec2str(self, vector):
        return (
            str(round(vector[0], 2))
            + " "
            + str(round(vector[1], 2))
            + " "
            + str(round(vector[2], 2))
        )

    def sel2com(self):
        """Get center of mass of the selection."""
        if self.selection:
            com = np.average(self.structure[self.selection].get_positions(), axis=0)
        else:
            com = [0, 0, 0]

        return com

    @property
    def action_vector(self):
        """Define the action vector."""
        normal = self.str2vec(self.axis_p2.value) - self.str2vec(self.axis_p1.value)
        return normal / np.linalg.norm(normal)

    def def_point(self, _=None):
        """Define the action point."""
        self.point.value = self.vec2str(self.sel2com())
        if self.autoclear_selection.value:
            self.input_selection = None
            self.input_selection = []

    def def_axis_p1(self, _=None):
        """Define the first point of axis."""
        self.axis_p1.value = self.vec2str(self.sel2com())
        if self.autoclear_selection.value:
            self.input_selection = None
            self.input_selection = []

    def def_axis_p2(self, _=None):
        """Define the second point of axis."""
        if not self.selection:
            self._status_message.message = """
            <div class="alert alert-info">
            <strong>Please select atoms first.</strong>
            </div>
            """
        else:
            com = (
                np.average(self.structure[self.selection].get_positions(), axis=0)
                if self.selection
                else [0, 0, 1]
            )
            self.axis_p2.value = self.vec2str(com)
            if self.autoclear_selection.value:
                self.input_selection = None
                self.input_selection = []

    def def_perpendicular_to_screen(self, _=None):
        """Define a normalized vector perpendicular to the screen."""
        cmr = self.camera_orientation
        if cmr:
            self.axis_p1.value = "0 0 0"
            versor = np.array([-cmr[2], -cmr[6], -cmr[10]]) / np.linalg.norm(
                [-cmr[2], -cmr[6], -cmr[10]]
            )
            self.axis_p2.value = self.vec2str(versor.tolist())

    @_register_structure
    @_register_selection
    def translate_dr(self, _=None, atoms=None, selection=None):
        """Translate by dr along the selected vector."""

        atoms.positions[self.selection] += np.array(
            self.action_vector * self.displacement.value
        )

        self.input_selection = None  # Clear selection.

        self.structure, self.input_selection = atoms, selection

    @_register_structure
    @_register_selection
    def translate_dxdydz(self, _=None, atoms=None, selection=None):
        """Translate by the selected XYZ delta."""

        # The action.
        atoms.positions[self.selection] += np.array(self.str2vec(self.dxyz.value))
        self.input_selection = None  # Clear selection.
        self.structure, self.input_selection = atoms, selection

    @_register_structure
    @_register_selection
    def translate_to_xyz(self, _=None, atoms=None, selection=None):
        """Translate to the selected XYZ position."""
        # The action.
        geo_center = np.average(self.structure[self.selection].get_positions(), axis=0)
        atoms.positions[self.selection] += self.str2vec(self.dxyz.value) - geo_center
        self.input_selection = None  # Clear selection.
        self.structure, self.input_selection = atoms, selection

    @_register_structure
    @_register_selection
    def rotate(self, _=None, atoms=None, selection=None):
        """Rotate atoms around selected point in space and vector."""

        # The action.
        rotated_subset = atoms[self.selection]
        vec = self.str2vec(self.vec2str(self.action_vector))
        center = self.str2vec(self.point.value)
        rotated_subset.rotate(self.phi.value, v=vec, center=center, rotate_cell=False)
        atoms.positions[self.selection] = rotated_subset.positions
        self.input_selection = None  # Clear selection.

        self.structure, self.input_selection = atoms, selection

    @_register_structure
    @_register_selection
    def mirror(self, _=None, norm=None, point=None, atoms=None, selection=None):
        """Mirror atoms on the plane perpendicular to the action vector."""
        # The action.
        # Vector and point define the mirrorring surface.
        p_normal = norm if norm is not None else self.action_vector
        p_point = point if point is not None else self.str2vec(self.point.value)

        # Check if norm vector makes sense.
        if np.isnan(p_normal).any() or np.linalg.norm(p_normal) < 1e-4:
            self._status_message.message = """
            <div class="alert alert-info">
            <strong>Norm vector not makes sense.</strong>
            </div>
            """
            return

        # Define vectors from p_point that point to the atoms which are to be moved.
        mirror_subset = atoms.positions[selection] - p_point

        # Project vectors onto the plane normal.
        projections = (
            p_normal
            * np.dot(mirror_subset, p_normal)[:, np.newaxis]
            / np.dot(p_normal, p_normal)
        )

        # Mirror atoms.
        atoms.positions[selection] -= 2 * projections

        self.input_selection = None  # Clear selection.

        self.structure, self.input_selection = atoms, selection

    def mirror_3p(self, _=None):
        """Mirror atoms on the plane containing action vector and action point."""
        pt1 = self.str2vec(self.axis_p2.value)
        pt2 = self.str2vec(self.axis_p1.value)
        pt3 = self.str2vec(self.point.value)
        normal = np.cross(pt1 - pt2, pt3 - pt2)
        normal = normal / np.linalg.norm(normal)
        self.mirror(norm=normal, point=pt3)

    @_register_structure
    @_register_selection
    def align(self, _=None, atoms=None, selection=None):
        """Rotate atoms to align action vector with XYZ vector."""
        if not self.selection:
            return

        # The action.
        center = self.str2vec(self.point.value)
        subset = atoms[selection]
        subset.rotate(self.action_vector, self.str2vec(self.dxyz.value), center=center)
        atoms.positions[selection] = subset.positions

        self.structure, self.input_selection = atoms, selection

    @_register_structure
    @_register_selection
    def mod_element(self, _=None, atoms=None, selection=None):
        """Modify selected atoms into the given element."""
        last_atom = atoms.get_global_number_of_atoms()

        if self.ligand.value == 0:
            for idx in self.selection:
                new = ase.Atom(self.element.value)
                atoms[idx].mass = new.mass
                atoms[idx].magmom = new.magmom
                atoms[idx].momentum = new.momentum
                atoms[idx].symbol = new.symbol
                atoms[idx].tag = new.tag
                atoms[idx].charge = new.charge
            new_selection = selection
        else:
            initial_ligand = self.ligand.rotate(
                align_to=self.action_vector, remove_anchor=True
            )

            for idx in self.selection:
                position = self.structure.positions[idx].copy()
                lgnd = initial_ligand.copy()
                lgnd.translate(position)
                atoms += lgnd
            new_selection = list(
                range(last_atom, last_atom + len(selection) * len(lgnd))
            )

        self.structure, self.input_selection = atoms, new_selection

    @_register_structure
    @_register_selection
    def copy_sel(self, _=None, atoms=None, selection=None):
        """Copy selected atoms and shift by 1.0 A along X-axis."""

        last_atom = atoms.get_global_number_of_atoms()

        # The action
        add_atoms = atoms[self.selection].copy()
        add_atoms.translate([1.0, 0, 0])
        atoms += add_atoms

        self.structure, self.input_selection = (
            atoms,
            list(range(last_atom, last_atom + len(selection))),
        )

    @_register_structure
    @_register_selection
    def add(self, _=None, atoms=None, selection=None):
        """Add atoms."""
        last_atom = atoms.get_global_number_of_atoms()
        if self.ligand.value == 0:
            initial_ligand = ase.Atoms([ase.Atom(self.element.value, [0, 0, 0])])
            rad = SYMBOL_RADIUS[self.element.value]
        else:
            initial_ligand = self.ligand.rotate(align_to=self.action_vector)
            rad = SYMBOL_RADIUS[self.ligand.anchoring_atom]

        for idx in self.selection:
            # It is important to copy, otherwise the initial structure will be modified
            position = self.structure.positions[idx].copy()
            lgnd = initial_ligand.copy()

            if self.bond_length.disabled:
                lgnd.translate(
                    position
                    + self.action_vector
                    * (SYMBOL_RADIUS[self.structure.symbols[idx]] + rad)
                )
            else:
                lgnd.translate(position + self.action_vector * self.bond_length.value)

            atoms += lgnd

        new_selection = list(range(last_atom, last_atom + len(selection) * len(lgnd)))

        # The order of the traitlets below is important -
        # we must be sure trait atoms is set before trait selection
        self.structure, self.input_selection = atoms, new_selection

    @_register_structure
    @_register_selection
    def remove(self, _=None, atoms=None, selection=None):
        """Remove selected atoms."""
        del [atoms[selection]]

        # The order of the traitlets below is important -
        # we must be sure trait atoms is set before trait selection
        self.structure = atoms
        self.input_selection = None
