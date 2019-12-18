"""Module to provide functionality to import structures."""
from __future__ import print_function
from __future__ import absolute_import

import os
import tempfile
import datetime
from collections import OrderedDict

import nglview
import ase.io

from traitlets import Bool

import ipywidgets as ipw
from fileupload import FileUploadWidget

from aiida.orm import CalcFunctionNode, CalcJobNode, Node, QueryBuilder, WorkChainNode, StructureData


class StructureUploadWidget(ipw.VBox):  # pylint: disable=too-many-instance-attributes
    '''Upload a structure and store it in AiiDA database.

    Useful class members:
    :ivar has_structure: whether the widget contains a structure
    :vartype has_structure: bool
    :ivar frozen: whenter the widget is frozen (can't be modified) or not
    :vartype frozen: bool
    :ivar structure_node: link to AiiDA structure object
    :vartype structure_node: StructureData or CifData
    '''
    has_structure = Bool(False)
    frozen = Bool(False)
    DATA_FORMATS = ('StructureData', 'CifData')

    def __init__(  # pylint: disable=too-many-arguments
            self,
            text="Upload Structure",
            storable=True,
            node_class=None,
            examples=None,
            data_importers=None,
            **kwargs):
        """
        :param text: Text to display before upload button
        :type text: str
        :param storable: Whether to provide Store button (together with Store format)
        :type storable: bool
        :param node_class: AiiDA node class for storing the structure.
            Possible values: 'StructureData', 'CifData' or None (let the user decide).
            Note: If your workflows require a specific node class, better fix it here.
        :param examples: list of tuples each containing a name and a path to an example structure
        :type examples: list
        :param data_importers: list of tuples each containing a name and an object for data importing. Each object
        should containt an empty `on_structure_selection()` method that has two parameters: structure_ase, name
        :type examples: list

        """
        self.name = None
        self.file_path = None
        examples = [] if examples is None else examples
        data_importers = [] if data_importers is None else data_importers
        self._structure_sources_tab = ipw.Tab()
        self.file_upload = FileUploadWidget(text)
        supported_formats = ipw.HTML(
            """<a href="https://wiki.fysik.dtu.dk/ase/_modules/ase/io/formats.html" target="_blank">
            Supported structure formats
            </a>""")

        self.select_example = ipw.Dropdown(options=self.get_example_structures(examples))
        self.viewer = nglview.NGLWidget()
        self.btn_store = ipw.Button(description='Store in AiiDA', disabled=True)
        self.structure_description = ipw.Text(placeholder="Description (optional)")

        self.structure_ase = None
        self._structure_node = None
        self.data_format = ipw.RadioButtons(options=self.DATA_FORMATS, description='Data type:')

        structure_sources = [("Upload", ipw.VBox([self.file_upload, supported_formats]))]

        if data_importers:
            for label, importer in data_importers:
                structure_sources.append((label, importer))
                importer.on_structure_selection = self.select_structure

        if examples:
            structure_sources.append(("Examples", self.select_example))

        if len(structure_sources) == 1:
            self._structure_sources_tab = structure_sources[0][1]
        else:
            self._structure_sources_tab.children = [s[1] for s in structure_sources]
            for i, source in enumerate(structure_sources):
                self._structure_sources_tab.set_title(i, source[0])

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
        super(StructureUploadWidget, self).__init__(children=[self._structure_sources_tab, self.viewer, store],
                                                    **kwargs)

        self.file_upload.observe(self._on_file_upload, names='data')
        self.select_example.observe(self._on_select_example, names=['value'])
        self.btn_store.on_click(self._on_click_store)
        self.data_format.observe(self.reset_structure, names=['value'])
        self.structure_description.observe(self.reset_structure, names=['value'])

    @staticmethod
    def get_example_structures(examples):
        """Get the list of example structures."""
        if not isinstance(examples, list):
            raise ValueError("parameter examples should be of type list, {} given".format(type(examples)))
        if examples:
            options = [("Select structure", False)]
            options += examples
            return options
        return []

    def _on_file_upload(self, change):  # pylint: disable=unused-argument
        """When file upload button is pressed."""
        self.file_path = os.path.join(tempfile.mkdtemp(), self.file_upload.filename)
        with open(self.file_path, 'w') as fobj:
            fobj.write(self.file_upload.data.decode("utf-8"))
        structure_ase = self.get_ase(self.file_path)
        self.select_structure(structure_ase=structure_ase, name=self.file_upload.filename)

    def _on_select_example(self, change):  # pylint: disable=unused-argument
        """When example is selected."""
        if self.select_example.value:
            structure_ase = self.get_ase(self.select_example.value)
            self.file_path = self.select_example.value
        else:
            structure_ase = False
        self.select_structure(structure_ase=structure_ase, name=self.select_example.label)

    def reset_structure(self, change=None):  # pylint: disable=unused-argument
        if self.frozen:
            return
        self._structure_node = None

    def select_structure(self, structure_ase, name):
        """Select structure

        :param structure_ase: ASE object containing structure
        :type structure_ase: ASE Atoms
        :param name: File name with extension but without path
        :type name: str
        """
        if self.frozen:
            return
        self.name = name
        self._structure_node = None
        if not structure_ase:
            self.btn_store.disabled = True
            self.has_structure = False
            self.structure_ase = None
            self.structure_description.value = ''

            self.reset_structure()
            self.refresh_view()
            return
        self.btn_store.disabled = False
        self.has_structure = True
        self.structure_description.value = self.get_description(structure_ase, name)
        self.structure_ase = structure_ase
        self.refresh_view()

    @staticmethod
    def get_ase(fname):
        """Get ASE structure object."""
        try:
            traj = ase.io.read(fname, index=":")
        except Exception as exc:  # pylint: disable=broad-except
            if exc.args:
                print(' '.join([str(c) for c in exc.args]))
            else:
                print("Unknown error")
            return False
        if not traj:
            print("Could not read any information from the file {}".format(fname))
            return False
        if len(traj) > 1:
            print("Warning: Uploaded file {} contained more than one structure. I take the first one.".format(fname))
        return traj[0]

    @staticmethod
    def get_description(structure_ase, name):
        formula = structure_ase.get_chemical_formula()
        return "{} ({})".format(formula, name)

    def refresh_view(self):
        """Reset the structure view."""
        viewer = self.viewer
        # Note: viewer.clear() only removes the 1st component
        # pylint: disable=protected-access
        for comp_id in viewer._ngl_component_ids:
            viewer.remove_component(comp_id)
        if self.structure_ase is None:
            return
        viewer.add_component(nglview.ASEStructure(self.structure_ase))  # adds ball+stick
        viewer.add_unitcell()  # pylint: disable=no-member

    # pylint: disable=unused-argument
    def _on_click_store(self, change):
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
        self.file_upload.disabled = True
        self.data_format.disabled = True
        self.select_example.disabled = True

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
            # determine data source
            if self.name.endswith('.cif'):
                source_format = 'CIF'
            else:
                source_format = 'ASE'
            # perform conversion
            if self.data_format.value == 'CifData':
                if source_format == 'CIF':
                    from aiida.orm.nodes.data.cif import CifData
                    self._structure_node = CifData(file=os.path.abspath(self.file_path),
                                                   scan_type='flex',
                                                   parse_policy='lazy')
                else:
                    from aiida.orm.nodes.data.cif import CifData
                    self._structure_node = CifData()
                    self._structure_node.set_ase(self.structure_ase)
            else:  # Target format is StructureData
                self._structure_node = StructureData(ase=self.structure_ase)
            self._structure_node.description = self.structure_description.value
            self._structure_node.label = os.path.splitext(self.name)[0]
        return self._structure_node


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

    def __init__(self):
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
        import pybel

        f_f = pybel._forcefields["mmff94"]
        if not f_f.Setup(mol.OBMol):
            f_f = pybel._forcefields["uff"]
            if not f_f.Setup(mol.OBMol):
                self.output.value = "Cannot set up forcefield"
                return

        # initial cleanup before the weighted search
        f_f.SteepestDescent(5500, 1.0e-9)
        f_f.WeightedRotorSearch(15000, 500)
        f_f.ConjugateGradients(6500, 1.0e-10)
        f_f.GetCoordinates(mol.OBMol)

    def _on_button_pressed(self, change):  # pylint: disable=unused-argument
        """Convert SMILES to ase structure when button is pressed."""
        import pybel
        if not self.smiles.value:
            return

        mol = pybel.readstring("smi", self.smiles.value)
        mol.make3D()

        pybel._builder.Build(mol.OBMol)
        mol.addh()
        self._optimize_mol(mol)

        structure_ase = self.pymol_2_ase(mol)
        formula = structure_ase.get_chemical_formula()
        if self.on_structure_selection is not None:
            self.on_structure_selection(structure_ase=structure_ase, name=formula)

    def on_structure_selection(self, structure_ase, name):
        pass
