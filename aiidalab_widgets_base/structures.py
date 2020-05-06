"""Module to provide functionality to import structures."""
# pylint: disable=no-self-use

import os
import tempfile
import datetime
from collections import OrderedDict
import numpy as np
import ipywidgets as ipw
from traitlets import Instance, Int, Set, Unicode, Union, link, default, observe, validate

# ASE imports
from ase import Atom, Atoms
from ase.data import chemical_symbols, covalent_radii

# AiiDA and AiiDA lab imports
from aiida.orm import CalcFunctionNode, CalcJobNode, Data, QueryBuilder, Node, WorkChainNode
from aiida.plugins import DataFactory
from .utils import get_ase_from_file
from .viewers import StructureDataViewer
from .data import LigandSelectorWidget

SYMBOL_RADIUS = {key: covalent_radii[i] for i, key in enumerate(chemical_symbols)}


class StructureManagerWidget(ipw.VBox):
    '''Upload a structure and store it in AiiDA database.

    Attributes:
        structure(Atoms): trait that contains the selected structure. 'None' if no structure is selected.
        structure_node(StructureData, CifData): trait that contains AiiDA structure object
        node_class(str): trait that contains structure_node type (as string).
    '''

    structure = Union([Instance(Atoms), Instance(Data)], allow_none=True)
    structure_node = Instance(Data, allow_none=True, read_only=True)
    node_class = Unicode()

    SUPPORTED_DATA_FORMATS = {'CifData': 'cif', 'StructureData': 'structure'}

    def __init__(self, importers, editors=None, storable=True, node_class=None, **kwargs):
        """
        Arguments:
            importers(list): list of tuples each containing the displayed name of importer and the
                importer object. Each object should containt 'structure' trait pointing to the imported
                structure. The trait will be linked to 'structure' trait of this class.

            storable(bool): Whether to provide Store button (together with Store format)

            node_class(str): AiiDA node class for storing the structure.
                Possible values: 'StructureData', 'CifData' or None (let the user decide).
                Note: If your workflows require a specific node class, better fix it here.
        """

        # Make sure the list is not empty
        if not importers:
            raise ValueError("The parameter importers should contain a list (or tuple) of tuples "
                             "(\"importer name\", importer), got a falsy object.")

        # Store button.
        self.btn_store = ipw.Button(description='Store in AiiDA', disabled=True)
        self.btn_store.on_click(self._on_click_store)

        # Setting traits' initial values
        self._inserted_structure = None

        # Structure viewer.
        self.viewer = StructureDataViewer(downloadable=False)
        link((self, 'structure'), (self.viewer, 'structure'))

        # Store format selector.
        data_format = ipw.RadioButtons(options=self.SUPPORTED_DATA_FORMATS, description='Data type:')
        link((data_format, 'label'), (self, 'node_class'))

        # Description that is stored along with the new structure.
        self.structure_label = ipw.Text(description='Label')
        self.structure_description = ipw.Text(description='Description')

        # Displaying structure importers.
        if len(importers) == 1:
            # If there is only one importer - no need to make tabs.
            self._structure_sources_tab = importers[0][1]
            # Assigning a function which will be called when importer provides a structure.
            link((self, 'structure'), (importers[0][1], 'structure'))
        else:
            self._structure_sources_tab = ipw.Tab()  # Tabs.
            self._structure_sources_tab.children = [i[1] for i in importers]  # One importer per tab.
            for i, (label, importer) in enumerate(importers):
                # Labeling tabs.
                self._structure_sources_tab.set_title(i, label)
                link((self, 'structure'), (importer, 'structure'))

        # Displaying structure editors
        if editors and len(editors) == 1:
            structure_editors_tab = editors[0][1]
            structure_editors_tab.manager = self
        elif editors:
            structure_editors_tab = ipw.Tab()
            structure_editors_tab.children = [i[1] for i in editors]
            for i, (label, editor) in enumerate(editors):
                structure_editors_tab.set_title(i, label)
                editor.manager = self
        else:
            structure_editors_tab = None

        # Store button, store class selector, description.
        store_and_description = [self.btn_store] if storable else []

        if node_class is None:
            store_and_description.append(data_format)
        elif node_class in self.SUPPORTED_DATA_FORMATS:
            self.node_class = node_class
        else:
            raise ValueError("Unknown data format '{}'. Options: {}".format(node_class,
                                                                            list(self.SUPPORTED_DATA_FORMATS.keys())))
        self.output = ipw.HTML('')

        store_and_description = ipw.HBox(store_and_description + [self.structure_label, self.structure_description])

        children = [self._structure_sources_tab, self.viewer, store_and_description]
        if structure_editors_tab:
            accordion = ipw.Accordion([structure_editors_tab])
            accordion.selected_index = None
            accordion.set_title(0, 'Edit Structure')
            children += [accordion]

        children += [self.output]
        super().__init__(children=children, **kwargs)

    def _on_click_store(self, change):  # pylint: disable=unused-argument
        self.store_structure()

    def store_structure(self):
        """Stores the structure in AiiDA database."""

        if self.structure_node is None:
            return
        if self.structure_node.is_stored:
            self.output.value = "Already stored in AiiDA [{}], skipping...".format(self.structure_node)
            return
        self.structure_node.label = self.structure_label.value
        self.structure_node.description = self.structure_description.value
        self.structure_node.store()
        self.output.value = "Stored in AiiDA [{}]".format(self.structure_node)

    @staticmethod
    @default('node_class')
    def _default_node_class():
        return 'StructureData'

    @observe('node_class')
    def _change_structure_node(self, _=None):
        self._structure_changed()

    @validate('structure')
    def _valid_structure(self, change):
        """Returns ASE atoms object and sets structure_node trait."""

        self._inserted_structure = change['value']

        # If structure trait is set to Atoms object, structure node must be generated
        if isinstance(self._inserted_structure, Atoms):
            return self._inserted_structure

        # If structure trait is set to AiiDA node, converting it to ASE Atoms object
        if isinstance(self._inserted_structure, Data):
            return self._inserted_structure.get_ase()

        return None

    @observe('structure')
    def _structure_changed(self, _=None):
        """Perform some operations that depend on the value of `structure` trait.

        This function enables/disables `btn_store` widget if structure is provided/set to None.
        Also, the function sets `structure_node` trait to the selected node type.
        """

        # If structure trait was set to None, structure_node should become None as well.
        if self.structure is None:
            self.set_trait('structure_node', None)
            self.btn_store.disabled = True
            return

        self.btn_store.disabled = False

        # Chosing type for the structure node.
        StructureNode = DataFactory(self.SUPPORTED_DATA_FORMATS[self.node_class])  # pylint: disable=invalid-name

        # If structure trait is set to Atoms object, structure node must be created from it.
        if isinstance(self._inserted_structure, Atoms):
            structure_node = StructureNode(ase=self._inserted_structure)

        # If structure trait is set to AiiDA node, converting it to ASE Atoms object
        elif isinstance(self._inserted_structure, Data):

            # Transform the structure to the StructureNode if needed.
            if isinstance(self._inserted_structure, StructureNode):
                structure_node = self._inserted_structure

            else:
                # self.structure was already converted to ASE Atoms object.
                structure_node = StructureNode(ase=self.structure)

        # Setting the structure_node trait.
        self.set_trait('structure_node', structure_node)
        self.structure_label.value = self.structure.get_chemical_formula()

    @default('structure_node')
    def _default_structure_node(self):
        return None


class StructureUploadWidget(ipw.VBox):
    """Class that allows to upload structures from user's computer."""
    structure = Instance(Atoms, allow_none=True)

    def __init__(self, text="Upload Structure"):
        from fileupload import FileUploadWidget

        self.file_path = None
        self.file_upload = FileUploadWidget(text)
        supported_formats = ipw.HTML(
            """<a href="https://wiki.fysik.dtu.dk/ase/_modules/ase/io/formats.html" target="_blank">
        Supported structure formats
        </a>""")
        self.file_upload.observe(self._on_file_upload, names='data')
        super().__init__(children=[self.file_upload, supported_formats])

    def _on_file_upload(self, change):  # pylint: disable=unused-argument
        """When file upload button is pressed."""
        self.file_path = os.path.join(tempfile.mkdtemp(), self.file_upload.filename)
        with open(self.file_path, 'w') as fobj:
            fobj.write(self.file_upload.data.decode("utf-8"))
        self.structure = get_ase_from_file(self.file_path)

    @default('structure')
    def _default_structure(self):
        return None


class StructureExamplesWidget(ipw.VBox):
    """Class to provide example structures for selection."""
    structure = Instance(Atoms, allow_none=True)

    def __init__(self, examples, **kwargs):
        self.on_structure_selection = lambda structure_ase, name: None
        self._select_structure = ipw.Dropdown(options=self.get_example_structures(examples))
        self._select_structure.observe(self._on_select_structure, names=['value'])
        super().__init__(children=[self._select_structure], **kwargs)

    @staticmethod
    def get_example_structures(examples):
        """Get the list of example structures."""
        if not isinstance(examples, list):
            raise ValueError("parameter examples should be of type list, {} given".format(type(examples)))
        return [("Select structure", False)] + examples

    def _on_select_structure(self, change):  # pylint: disable=unused-argument
        """When structure is selected."""

        self.structure = get_ase_from_file(self._select_structure.value) if self._select_structure.value else None

    @default('structure')
    def _default_structure(self):
        return None


class StructureBrowserWidget(ipw.VBox):
    """Class to query for structures stored in the AiiDA database."""
    structure = Union([Instance(Atoms), Instance(Data)], allow_none=True)

    def __init__(self):

        # Structure objects we want to query for.
        self.query_structure_type = (DataFactory('structure'), DataFactory('cif'))

        # Extracting available process labels.
        qbuilder = QueryBuilder().append((CalcJobNode, WorkChainNode), project="label")
        self.drop_label = ipw.Dropdown(options=sorted({'All'}.union({i[0] for i in qbuilder.iterall() if i[0]})),
                                       value='All',
                                       description='Process Label',
                                       disabled=True,
                                       style={'description_width': '120px'},
                                       layout={'width': '50%'})
        self.drop_label.observe(self.search, names='value')

        # Disable process labels selection if we are not looking for the calculated structures.
        def disable_drop_label(change):
            self.drop_label.disabled = not change['new'] == 'calculated'

        # Select structures kind.
        self.mode = ipw.RadioButtons(options=['all', 'uploaded', 'edited', 'calculated'], layout={'width': '25%'})
        self.mode.observe(self.search, names='value')
        self.mode.observe(disable_drop_label, names='value')

        # Date range.
        # Note: there is Date picker widget, but it currently does not work in Safari:
        # https://ipywidgets.readthedocs.io/en/latest/examples/Widget%20List.html#Date-picker
        date_text = ipw.HTML(value='<p>Select the date range:</p>')
        self.start_date_widget = ipw.Text(value='', description='From: ', style={'description_width': '120px'})
        self.end_date_widget = ipw.Text(value='', description='To: ')

        # Search button.
        btn_search = ipw.Button(description='Search',
                                button_style='info',
                                layout={
                                    'width': 'initial',
                                    'margin': '2px 0 0 2em'
                                })
        btn_search.on_click(self.search)

        age_selection = ipw.VBox(
            [date_text, ipw.HBox([self.start_date_widget, self.end_date_widget, btn_search])],
            layout={
                'border': '1px solid #fafafa',
                'padding': '1em'
            })

        h_line = ipw.HTML('<hr>')
        box = ipw.VBox([age_selection, h_line, ipw.HBox([self.mode, self.drop_label])])

        self.results = ipw.Dropdown(layout={'width': '900px'})
        self.results.observe(self._on_select_structure)
        self.search()
        super().__init__([box, h_line, self.results])

    def preprocess(self):
        """Search structures in AiiDA database and add formula extra to them."""

        queryb = QueryBuilder()
        queryb.append(self.query_structure_type, filters={'extras': {'!has_key': 'formula'}})
        for item in queryb.all():  # iterall() would interfere with set_extra()
            try:
                formula = item[0].get_formula()
            except AttributeError:
                # Slow part.
                formula = item[0].get_ase().get_chemical_formula()
            item[0].set_extra("formula", formula)

    def search(self, _=None):
        """Launch the search of structures in AiiDA database."""
        self.preprocess()

        qbuild = QueryBuilder()

        # If the date range is valid, use it for the search
        try:
            start_date = datetime.datetime.strptime(self.start_date_widget.value, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(self.end_date_widget.value, '%Y-%m-%d') + datetime.timedelta(hours=24)

        # Otherwise revert to the standard (i.e. last 7 days)
        except ValueError:
            start_date = datetime.datetime.now() - datetime.timedelta(days=7)
            end_date = datetime.datetime.now() + datetime.timedelta(hours=24)

            self.start_date_widget.value = start_date.strftime('%Y-%m-%d')
            self.end_date_widget.value = end_date.strftime('%Y-%m-%d')

        filters = {}
        filters['ctime'] = {'and': [{'>': start_date}, {'<=': end_date}]}

        if self.mode.value == "uploaded":
            qbuild2 = QueryBuilder().append(self.query_structure_type, project=["id"],
                                            tag='structures').append(Node, with_outgoing='structures')
            processed_nodes = [n[0] for n in qbuild2.all()]
            if processed_nodes:
                filters['id'] = {"!in": processed_nodes}
            qbuild.append(self.query_structure_type, filters=filters)

        elif self.mode.value == "calculated":
            if self.drop_label.value == 'All':
                qbuild.append((CalcJobNode, WorkChainNode), tag='calcjobworkchain')
            else:
                qbuild.append((CalcJobNode, WorkChainNode),
                              filters={'label': self.drop_label.value},
                              tag='calcjobworkchain')
            qbuild.append(self.query_structure_type, with_incoming='calcjobworkchain', filters=filters)

        elif self.mode.value == "edited":
            qbuild.append(CalcFunctionNode)
            qbuild.append(self.query_structure_type, with_incoming=CalcFunctionNode, filters=filters)

        elif self.mode.value == "all":
            qbuild.append(self.query_structure_type, filters=filters)

        qbuild.order_by({self.query_structure_type: {'ctime': 'desc'}})
        matches = {n[0] for n in qbuild.iterall()}
        matches = sorted(matches, reverse=True, key=lambda n: n.ctime)

        options = OrderedDict()
        options["Select a Structure ({} found)".format(len(matches))] = False

        for mch in matches:
            label = "PK: {}".format(mch.id)
            label += " | " + mch.ctime.strftime("%Y-%m-%d %H:%M")
            label += " | " + mch.get_extra("formula")
            label += " | " + mch.node_type.split('.')[-2]
            label += " | " + mch.label
            label += " | " + mch.description
            options[label] = mch

        self.results.options = options

    def _on_select_structure(self, _=None):
        self.structure = self.results.value or None

    @default('structure')
    def _default_structure(self):
        return None


class SmilesWidget(ipw.VBox):
    """Conver SMILES into 3D structure."""
    structure = Instance(Atoms, allow_none=True)

    SPINNER = """<i class="fa fa-spinner fa-pulse" style="color:red;" ></i>"""

    def __init__(self):
        try:
            import openbabel  # pylint: disable=unused-import
        except ImportError:
            super().__init__(
                [ipw.HTML("The SmilesWidget requires the OpenBabel library, "
                          "but the library was not found.")])
            return

        self.smiles = ipw.Text()
        self.create_structure_btn = ipw.Button(description="Generate molecule", button_style='info')
        self.create_structure_btn.on_click(self._on_button_pressed)
        self.output = ipw.HTML("")
        super().__init__([self.smiles, self.create_structure_btn, self.output])

    @staticmethod
    def pymol_2_ase(pymol):
        """Convert pymol object into ASE Atoms."""

        asemol = Atoms()
        for atm in pymol.atoms:
            asemol.append(Atom(chemical_symbols[atm.atomicnum], atm.coords))
        asemol.cell = np.amax(asemol.positions, axis=0) - np.amin(asemol.positions, axis=0) + [10] * 3
        asemol.pbc = True
        asemol.center()
        return asemol

    def _optimize_mol(self, mol):
        """Optimize a molecule using force field (needed for complex SMILES)."""

        # Note, the pybel module imported below comes together with openbabel package. Do not confuse it with
        # pybel package available on PyPi: https://pypi.org/project/pybel/
        import pybel  # pylint:disable=import-error

        self.output.value = "Screening possible conformers {}".format(self.SPINNER)  #font-size:20em;

        f_f = pybel._forcefields["mmff94"]  # pylint: disable=protected-access
        if not f_f.Setup(mol.OBMol):
            f_f = pybel._forcefields["uff"]  # pylint: disable=protected-access
            if not f_f.Setup(mol.OBMol):
                self.output.value = "Cannot set up forcefield"
                return

        # initial cleanup before the weighted search
        f_f.SteepestDescent(5500, 1.0e-9)
        f_f.WeightedRotorSearch(15000, 500)
        f_f.ConjugateGradients(6500, 1.0e-10)
        f_f.GetCoordinates(mol.OBMol)
        self.output.value = ""

    def _on_button_pressed(self, change):  # pylint: disable=unused-argument
        """Convert SMILES to ase structure when button is pressed."""
        self.output.value = ""

        # Note, the pybel module imported below comes together with openbabel package. Do not confuse it with
        # pybel package available on PyPi: https://pypi.org/project/pybel/
        import pybel  # pylint:disable=import-error

        if not self.smiles.value:
            return

        mol = pybel.readstring("smi", self.smiles.value)
        self.output.value = """SMILES to 3D conversion {}""".format(self.SPINNER)
        mol.make3D()

        pybel._builder.Build(mol.OBMol)  # pylint: disable=protected-access
        mol.addh()
        self._optimize_mol(mol)
        self.structure = self.pymol_2_ase(mol)

    @default('structure')
    def _default_structure(self):
        return None


class BasicStructureEditor(ipw.VBox):
    """Widget that allows for the basic structure editing."""

    manager = Instance(StructureManagerWidget, allow_none=True)
    structure = Instance(Atoms, allow_none=True)
    selection = Set(Int)

    def __init__(self):

        # Define action vector.
        self.axis_p1 = ipw.Text(description='Starting point', value='0 0 0', layout={'width': 'initial'})
        self.axis_p2 = ipw.Text(description='Ending point', value='0 0 1', layout={'width': 'initial'})
        btn_def_atom1 = ipw.Button(description='From selection', layout={'width': 'initial'})
        btn_def_atom1.on_click(self.def_axis_p1)
        btn_def_atom2 = ipw.Button(description='From selection', layout={'width': 'initial'})
        btn_def_atom2.on_click(self.def_axis_p2)
        btn_get_from_camera = ipw.Button(description='Perp. to screen',
                                         button_style='warning',
                                         layout={'width': 'initial'})
        btn_get_from_camera.on_click(self.def_perpendicular_to_screen)

        # Define action point.
        self.point = ipw.Text(description='Action point', value='0 0 0', layout={'width': 'initial'})
        btn_def_pnt = ipw.Button(description='From selection', layout={'width': 'initial'})
        btn_def_pnt.on_click(self.def_point)

        # Move atoms.
        btn_move_dr = ipw.Button(description='Move', layout={'width': 'initial'})
        btn_move_dr.on_click(self.translate_dr)
        self.displacement = ipw.FloatText(description='Move along the action vector',
                                          value=1,
                                          step=0.1,
                                          style={'description_width': 'initial'},
                                          layout={'width': 'initial'})

        btn_move_dxyz = ipw.Button(description='Move', layout={'width': 'initial'})
        btn_move_dxyz.on_click(self.translate_dxdydz)
        self.dxyz = ipw.Text(description='Move along (XYZ)',
                             value='0 0 0',
                             style={'description_width': 'initial'},
                             layout={
                                 'width': 'initial',
                                 'margin': '0px 0px 0px 20px'
                             })
        # Rotate atoms.
        btn_rotate = ipw.Button(description='Rotate', layout={'width': '10%'})
        btn_rotate.on_click(self.rotate)
        self.phi = ipw.FloatText(description='Rotate around the action vector which starts from the action point',
                                 value=0,
                                 step=5,
                                 style={'description_width': 'initial'},
                                 layout={'width': 'initial'})

        # Atoms selection.
        self.element = ipw.Dropdown(
            description="Select element",
            options=chemical_symbols[1:],
            value="H",
            style={'description_width': 'initial'},
            layout={'width': 'initial'},
        )

        def disable_element(_=None):
            if self.ligand.value == 0:
                self.element.disabled = False
            else:
                self.element.disabled = True

        # Ligand selection.
        self.ligand = LigandSelectorWidget()
        self.ligand.observe(disable_element, names='value')

        # Add atom.
        btn_add = ipw.Button(description='Add to selected', layout={'width': 'initial'})
        btn_add.on_click(self.add)
        self.bond_length = ipw.FloatText(description="Bond lenght.", value=1.0, layout={'width': '140px'})
        self.use_covalent_radius = ipw.Checkbox(
            value=False,
            description='Use covalent radius',
            style={'description_width': 'initial'},
        )
        self.use_covalent_radius.observe(self._observe_use_cov_radius, names='value')

        # Modify atom.
        btn_modify = ipw.Button(description='Modify selected', button_style='warning', layout={'width': 'initial'})
        btn_modify.on_click(self.mod_element)

        # Remove atom.
        btn_remove = ipw.Button(description='Remove selected', button_style='danger', layout={'width': 'initial'})
        btn_remove.on_click(self.remove)

        super().__init__(children=[
            ipw.HTML("<b>Action vector and point:</b>", layout={'margin': '20px 0px 10px 0px'}),
            ipw.HBox([self.axis_p1, btn_def_atom1, self.axis_p2, btn_def_atom2, btn_get_from_camera],
                     layout={'margin': '0px 0px 0px 20px'}),
            ipw.HBox([self.point, btn_def_pnt], layout={'margin': '0px 0px 0px 20px'}),
            ipw.HTML("<b>Move atom(s):</b>", layout={'margin': '20px 0px 10px 0px'}),
            ipw.HBox([self.displacement, btn_move_dr, self.dxyz, btn_move_dxyz], layout={'margin': '0px 0px 0px 20px'}),
            ipw.HBox([self.phi, btn_rotate], layout={'margin': '0px 0px 0px 20px'}),
            ipw.HTML("<b>Modify atom(s):</v>", layout={'margin': '20px 0px 10px 0px'}),
            ipw.HBox([self.element, self.ligand], layout={'margin': '0px 0px 0px 20px'}),
            ipw.HBox([
                btn_modify,
                btn_add,
                self.bond_length,
                self.use_covalent_radius,
            ],
                     layout={'margin': '0px 0px 0px 20px'}),
            ipw.HBox([btn_remove], layout={'margin': '0px 0px 0px 20px'}),
        ])

    @observe('manager')
    def _change_manager(self, value):
        """Set structure manager trait."""
        manager = value['new']
        if manager is None:
            return
        link((manager, 'structure'), (self, 'structure'))
        link((self, 'selection'), (manager.viewer, 'selection'))

    def _observe_use_cov_radius(self, _=None):
        if self.use_covalent_radius.value:
            self.bond_length.disabled = True
        else:
            self.bond_length.disabled = False

    def str2vec(self, string):
        return np.array(list(map(float, string.split())))

    def vec2str(self, vector):
        return str(round(vector[0], 2)) + ' ' + str(round(vector[1], 2)) + ' ' + str(round(vector[2], 2))

    def sel2com(self):
        """Get center of mass of the selection."""
        selection = list(self.selection)
        if selection:
            com = self.structure[selection].get_center_of_mass()
        else:
            com = [0, 0, 0]

        return com

    @property
    def action_vector(self):
        normal = self.str2vec(self.axis_p2.value) - self.str2vec(self.axis_p1.value)
        return normal / np.linalg.norm(normal)

    def def_point(self, _=None):
        self.point.value = self.vec2str(self.sel2com())

    def def_axis_p1(self, _=None):
        self.axis_p1.value = self.vec2str(self.sel2com())

    def def_axis_p2(self, _=None):
        com = self.structure[list(self.selection)].get_center_of_mass() if self.selection else [0, 0, 1]
        self.axis_p2.value = self.vec2str(com)

    def def_perpendicular_to_screen(self, _=None):
        cmr = self.manager.viewer._viewer._camera_orientation  # pylint: disable=protected-access
        if cmr:
            self.axis_p1.value = "0 0 0"
            self.axis_p2.value = self.vec2str([-cmr[2], -cmr[6], -cmr[10]])

    def translate_dr(self, _=None):
        """Translate by dr along the selected vector."""
        atoms = self.structure.copy()
        selection = self.selection

        atoms.positions[list(self.selection)] += np.array(self.action_vector * self.displacement.value)

        self.structure = atoms
        self.selection = selection

    def translate_dxdydz(self, _=None):
        """Translate along the selected vector."""
        selection = self.selection
        atoms = self.structure.copy()

        # The action.
        atoms.positions[list(self.selection)] += np.array(self.str2vec(self.dxyz.value))

        self.structure = atoms
        self.selection = selection

    def rotate(self, _=None):
        """Rotate atoms around selected point in space and vector."""

        selection = self.selection
        atoms = self.structure.copy()

        # The action.
        rotated_subset = atoms[list(self.selection)]
        vec = self.str2vec(self.vec2str(self.action_vector))
        center = self.str2vec(self.point.value)
        rotated_subset.rotate(self.phi.value, v=vec, center=center, rotate_cell=False)
        atoms.positions[list(self.selection)] = rotated_subset.positions

        self.structure = atoms
        self.selection = selection

    def mod_element(self, _=None):
        """Modify selected atoms into the given element."""
        atoms = self.structure.copy()
        selection = self.selection

        if self.ligand.value == 0:
            for idx in self.selection:
                atoms[idx].symbol = self.element.value
        else:
            initial_ligand = self.ligand.rotate(align_to=self.action_vector, remove_anchor=True)
            for idx in self.selection:
                position = self.structure.positions[idx].copy()
                lgnd = initial_ligand.copy()
                lgnd.translate(position)
                atoms += lgnd

        self.structure = atoms
        self.selection = selection

    def add(self, _=None):
        """Add atoms."""
        atoms = self.structure.copy()
        selection = self.selection

        if self.ligand.value == 0:
            initial_ligand = Atoms([Atom(self.element.value, [0, 0, 0])])
            rad = SYMBOL_RADIUS[self.element.value]
        else:
            initial_ligand = self.ligand.rotate(align_to=self.action_vector)
            rad = SYMBOL_RADIUS[self.ligand.anchoring_atom]

        for idx in self.selection:
            # It is important to copy, otherwise the initial structure will be modified
            position = self.structure.positions[idx].copy()
            lgnd = initial_ligand.copy()

            if self.use_covalent_radius.value:
                lgnd.translate(position + self.action_vector * (SYMBOL_RADIUS[self.structure.symbols[idx]] + rad))
            else:
                lgnd.translate(position + self.action_vector * self.bond_length.value)

            atoms += lgnd

        self.structure = atoms
        self.selection = selection

    def remove(self, _):
        """Remove selected atoms."""
        atoms = self.structure.copy()
        del [atoms[list(self.selection)]]
        self.structure = atoms
