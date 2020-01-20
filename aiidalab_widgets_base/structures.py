"""Module to provide functionality to import structures."""

import os
import tempfile
import datetime
from collections import OrderedDict
from traitlets import Bool
import ipywidgets as ipw

from aiida.orm import CalcFunctionNode, CalcJobNode, Node, QueryBuilder, WorkChainNode, StructureData
from .utils import get_ase_from_file


class StructureManagerWidget(ipw.VBox):  # pylint: disable=too-many-instance-attributes
    '''Upload a structure and store it in AiiDA database.

    Useful class members:
    :ivar has_structure: whether the widget contains a structure
    :vartype has_structure: bool
    :ivar frozen: whenter the widget is frozen (can't be modified) or not
    :vartype frozen: bool
    :ivar structure_node: link to AiiDA structure object
    :vartype structure_node: StructureData or CifData'''

    has_structure = Bool(False)
    frozen = Bool(False)
    DATA_FORMATS = ('StructureData', 'CifData')

    def __init__(self, importers, storable=True, node_class=None, **kwargs):
        """
        :param storable: Whether to provide Store button (together with Store format)
        :type storable: bool
        :param node_class: AiiDA node class for storing the structure.
            Possible values: 'StructureData', 'CifData' or None (let the user decide).
            Note: If your workflows require a specific node class, better fix it here.
        :param examples: list of tuples each containing a name and a path to an example structure
        :type examples: list
        :param importers: list of tuples each containing a name and an object for data importing. Each object
        should containt an empty `on_structure_selection()` method that has two parameters: structure_ase, name
        :type examples: list"""

        from .viewers import StructureDataViewer
        if not importers:  # we make sure the list is not empty
            raise ValueError("The parameter importers should contain a list (or tuple) of tuples "
                             "(\"importer name\", importer), got a falsy object.")

        self.structure_ase = None
        self._structure_node = None

        self.viewer = StructureDataViewer(downloadable=False)

        self.btn_store = ipw.Button(description='Store in AiiDA', disabled=True)
        self.btn_store.on_click(self._on_click_store)

        # Description that will is stored along with the new structure.
        self.structure_description = ipw.Text(placeholder="Description (optional)")

        # Select format to store in the AiiDA database.
        self.data_format = ipw.RadioButtons(options=self.DATA_FORMATS, description='Data type:')
        self.data_format.observe(self.reset_structure, names=['value'])

        if len(importers) == 1:
            # If there is only one importer - no need to make tabs.
            self._structure_sources_tab = importers[0][1]
            # Assigning a function which will be called when importer provides a structure.
            importers[0][1].on_structure_selection = self.select_structure
        else:
            self._structure_sources_tab = ipw.Tab()  # Tabs.
            self._structure_sources_tab.children = [i[1] for i in importers]  # One importer per tab.
            for i, (label, importer) in enumerate(importers):
                # Labeling tabs.
                self._structure_sources_tab.set_title(i, label)
                # Assigning a function which will be called when importer provides a structure.
                importer.on_structure_selection = self.select_structure

        if storable:
            if node_class is None:
                store = [self.btn_store, self.data_format, self.structure_description]
            elif node_class not in self.DATA_FORMATS:
                raise ValueError("Unknown data format '{}'. Options: {}".format(node_class, self.DATA_FORMATS))
            else:
                self.data_format.value = node_class
                store = [self.btn_store, self.structure_description]
        else:
            store = [self.structure_description]
        store = ipw.HBox(store)

        super().__init__(children=[self._structure_sources_tab, self.viewer, store], **kwargs)

    def reset_structure(self, change=None):  # pylint: disable=unused-argument
        if self.frozen:
            return
        self._structure_node = None
        self.viewer.structure = None

    def select_structure(self, structure_ase, name):
        """Select structure

        :param structure_ase: ASE object containing structure
        :type structure_ase: ASE Atoms
        :param name: File name with extension but without path
        :type name: str"""

        if self.frozen:
            return
        self._structure_node = None
        if not structure_ase:
            self.btn_store.disabled = True
            self.has_structure = False
            self.structure_ase = None
            self.structure_description.value = ''
            self.reset_structure()
            return
        self.btn_store.disabled = False
        self.has_structure = True
        self.structure_description.value = "{} ({})".format(structure_ase.get_chemical_formula(), name)
        self.structure_ase = structure_ase
        self.viewer.structure = structure_ase

    def _on_click_store(self, change):  # pylint: disable=unused-argument
        self.store_structure()

    def store_structure(self, label=None, description=None):
        """Stores the structure in AiiDA database."""
        if self.frozen:
            return
        if self.structure_node is None:
            return
        if self.structure_node.is_stored:
            print("Already stored in AiiDA: " + repr(self.structure_node) + " skipping..")
            return
        if label:
            self.structure_node.label = label
        if description:
            self.structure_node.description = description
        self.structure_node.store()
        print("Stored in AiiDA: " + repr(self.structure_node))

    def freeze(self):
        """Do not allow any further modifications"""
        self._structure_sources_tab.layout.visibility = 'hidden'
        self.frozen = True
        self.btn_store.disabled = True
        self.structure_description.disabled = True
        self.data_format.disabled = True

    @property
    def node_class(self):
        return self.data_format.value

    @node_class.setter
    def node_class(self, value):
        if self.frozen:
            return
        self.data_format.value = value

    @property
    def structure_node(self):
        """Returns AiiDA StructureData node."""
        if self._structure_node is None:
            if self.structure_ase is None:
                return None
            # perform conversion
            if self.data_format.value == 'CifData':
                from aiida.orm.nodes.data.cif import CifData
                self._structure_node = CifData()
                self._structure_node.set_ase(self.structure_ase)
            else:  # Target format is StructureData
                self._structure_node = StructureData(ase=self.structure_ase)
            self._structure_node.description = self.structure_description.value
            self._structure_node.label = self.structure_ase.get_chemical_formula()
        return self._structure_node


class StructureUploadWidget(ipw.VBox):
    """Class that allows to upload structures from user's computer."""

    def __init__(self, text="Upload Structure"):
        from fileupload import FileUploadWidget

        self.on_structure_selection = lambda structure_ase, name: None
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
        structure_ase = get_ase_from_file(self.file_path)
        self.on_structure_selection(structure_ase=structure_ase, name=self.file_upload.filename)


class StructureExamplesWidget(ipw.VBox):
    """Class to provide example structures for selection."""

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
        if not self._select_structure.value:
            return
        structure_ase = get_ase_from_file(self._select_structure.value)
        self.on_structure_selection(structure_ase=structure_ase, name=self._select_structure.label)


class StructureBrowserWidget(ipw.VBox):
    """Class to query for structures stored in the AiiDA database."""

    def __init__(self):
        # Find all process labels
        qbuilder = QueryBuilder()
        qbuilder.append(WorkChainNode, project="label")
        qbuilder.order_by({WorkChainNode: {'ctime': 'desc'}})
        process_labels = {i[0] for i in qbuilder.all() if i[0]}

        layout = ipw.Layout(width="900px")
        self.mode = ipw.RadioButtons(options=['all', 'uploaded', 'edited', 'calculated'],
                                     layout=ipw.Layout(width="25%"))

        # Date range
        self.dt_now = datetime.datetime.now()
        self.dt_end = self.dt_now - datetime.timedelta(days=10)
        self.date_start = ipw.Text(value='', description='From: ', style={'description_width': '120px'})

        self.date_end = ipw.Text(value='', description='To: ')
        self.date_text = ipw.HTML(value='<p>Select the date range:</p>')
        self.btn_date = ipw.Button(description='Search', layout={'margin': '1em 0 0 0'})
        self.age_selection = ipw.VBox(
            [self.date_text, ipw.HBox([self.date_start, self.date_end]), self.btn_date],
            layout={
                'border': '1px solid #fafafa',
                'padding': '1em'
            })

        # Labels
        self.drop_label = ipw.Dropdown(options=({'All'}.union(process_labels)),
                                       value='All',
                                       description='Process Label',
                                       style={'description_width': '120px'},
                                       layout={'width': '50%'})

        self.btn_date.on_click(self.search)
        self.mode.observe(self.search, names='value')
        self.drop_label.observe(self.search, names='value')

        h_line = ipw.HTML('<hr>')
        box = ipw.VBox([self.age_selection, h_line, ipw.HBox([self.mode, self.drop_label])])

        self.results = ipw.Dropdown(layout=layout)
        self.results.observe(self._on_select_structure)
        self.search()
        super(StructureBrowserWidget, self).__init__([box, h_line, self.results])

    @staticmethod
    def preprocess():
        """Search structures in AiiDA database."""
        queryb = QueryBuilder()
        queryb.append(StructureData, filters={'extras': {'!has_key': 'formula'}})
        for itm in queryb.all():  # iterall() would interfere with set_extra()
            formula = itm[0].get_formula()
            itm[0].set_extra("formula", formula)

    def search(self, change=None):  # pylint: disable=unused-argument
        """Launch the search of structures in AiiDA database."""
        self.preprocess()

        qbuild = QueryBuilder()
        try:  # If the date range is valid, use it for the search
            self.start_date = datetime.datetime.strptime(self.date_start.value, '%Y-%m-%d')
            self.end_date = datetime.datetime.strptime(self.date_end.value, '%Y-%m-%d') + datetime.timedelta(hours=24)
        except ValueError:  # Otherwise revert to the standard (i.e. last 7 days)
            self.start_date = self.dt_end
            self.end_date = self.dt_now + datetime.timedelta(hours=24)

            self.date_start.value = self.start_date.strftime('%Y-%m-%d')
            self.date_end.value = self.end_date.strftime('%Y-%m-%d')

        filters = {}
        filters['ctime'] = {'and': [{'<=': self.end_date}, {'>': self.start_date}]}
        if self.drop_label.value != 'All':
            qbuild.append(WorkChainNode, filters={'label': self.drop_label.value})
            #             print(qbuild.all())
            #             qbuild.append(CalcJobNode, with_incoming=WorkChainNode)
            qbuild.append(StructureData, with_incoming=WorkChainNode, filters=filters)
        else:
            if self.mode.value == "uploaded":
                qbuild2 = QueryBuilder()
                qbuild2.append(StructureData, project=["id"])
                qbuild2.append(Node, with_outgoing=StructureData)
                processed_nodes = [n[0] for n in qbuild2.all()]
                if processed_nodes:
                    filters['id'] = {"!in": processed_nodes}
                qbuild.append(StructureData, filters=filters)

            elif self.mode.value == "calculated":
                qbuild.append(CalcJobNode)
                qbuild.append(StructureData, with_incoming=CalcJobNode, filters=filters)

            elif self.mode.value == "edited":
                qbuild.append(CalcFunctionNode)
                qbuild.append(StructureData, with_incoming=CalcFunctionNode, filters=filters)

            elif self.mode.value == "all":
                qbuild.append(StructureData, filters=filters)

        qbuild.order_by({StructureData: {'ctime': 'desc'}})
        matches = {n[0] for n in qbuild.iterall()}
        matches = sorted(matches, reverse=True, key=lambda n: n.ctime)

        options = OrderedDict()
        options["Select a Structure ({} found)".format(len(matches))] = False

        for mch in matches:
            label = "PK: %d" % mch.pk
            label += " | " + mch.ctime.strftime("%Y-%m-%d %H:%M")
            label += " | " + mch.get_extra("formula")
            label += " | " + mch.description
            options[label] = mch

        self.results.options = options

    def _on_select_structure(self, change):  # pylint: disable=unused-argument
        """When a structure was selected."""
        if not self.results.value:
            return
        structure_ase = self.results.value.get_ase()
        formula = structure_ase.get_chemical_formula()
        if self.on_structure_selection is not None:
            self.on_structure_selection(structure_ase=structure_ase, name=formula)

    def on_structure_selection(self, structure_ase, name):
        pass


class SmilesWidget(ipw.VBox):
    """Conver SMILES into 3D structure."""

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
        import numpy as np
        from ase import Atoms, Atom
        from ase.data import chemical_symbols

        asemol = Atoms()
        for atm in pymol.atoms:
            asemol.append(Atom(chemical_symbols[atm.atomicnum], atm.coords))
        asemol.cell = np.amax(asemol.positions, axis=0) - np.amin(asemol.positions, axis=0) + [10] * 3
        asemol.pbc = True
        asemol.center()
        return asemol

    def _optimize_mol(self, mol):
        """Optimize a molecule using force field (needed for complex SMILES)."""
        from openbabel import pybel  # pylint:disable=import-error

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
        from openbabel import pybel  # pylint:disable=import-error
        if not self.smiles.value:
            return

        mol = pybel.readstring("smi", self.smiles.value)
        self.output.value = """SMILES to 3D conversion {}""".format(self.SPINNER)
        mol.make3D()

        pybel._builder.Build(mol.OBMol)  # pylint: disable=protected-access
        mol.addh()
        self._optimize_mol(mol)

        structure_ase = self.pymol_2_ase(mol)
        formula = structure_ase.get_chemical_formula()
        if self.on_structure_selection is not None:
            self.on_structure_selection(structure_ase=structure_ase, name=formula)

    def on_structure_selection(self, structure_ase, name):
        pass
