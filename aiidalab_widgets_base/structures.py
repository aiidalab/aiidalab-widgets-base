from __future__ import print_function
from __future__ import absolute_import

import os
import ase.io
import ipywidgets as ipw
from fileupload import FileUploadWidget
import tempfile
import nglview
from traitlets import Bool


class StructureUploadWidget(ipw.VBox):
    '''Upload a structure and store it in AiiDA database.

    Useful class members:
    :ivar has_structure: whether the widget contains a structure
    :vartype arg: bool
    :ivar frozen: whenter the widget is frozen (can't be modified) or not
    :vartype frozen: bool
    :ivar structure_node: link to AiiDA structure object
    :vartype structure_node: StructureData or CifData
    '''
    has_structure = Bool(False)
    frozen = Bool(False)
    DATA_FORMATS = ('StructureData', 'CifData')

    def __init__(self,
                 text="Upload Structure",
                 storable=True,
                 node_class=None,
                 examples=None,
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

        """
        examples = examples or []
        self._structure_sources_tab = ipw.Tab()

        self.file_upload = FileUploadWidget(text)
        supported_formats = ipw.HTML(
            """All supported structure formats are listed
        <a href="https://wiki.fysik.dtu.dk/ase/_modules/ase/io/formats.html" target="_blank">here</a>"""
        )

        self.select_example = ipw.Dropdown(
            options=self.get_example_structures(examples),
            description='Or choose from examples:',
            style={'description_width': '160px'},
        )

        self.viewer = nglview.NGLWidget()
        self.btn_store = ipw.Button(description='Store in AiiDA',
                                    disabled=True)
        self.structure_description = ipw.Text(
            placeholder="Description (optional)")

        self.structure_ase = None
        self._structure_node = None
        self.data_format = ipw.RadioButtons(options=self.DATA_FORMATS,
                                            description='Data type:')

        structure_sources = [ipw.VBox([self.file_upload, supported_formats])]
        structure_sources_names = ["Upload"]
        if examples:
            structure_sources.append(self.select_example)
            structure_sources_names.append("Take from examples")

        if len(structure_sources) == 1:
            self._structure_sources_tab = structure_sources[0]
        else:
            self._structure_sources_tab.children = structure_sources
            for i, title in enumerate(structure_sources_names):
                self._structure_sources_tab.set_title(i, title)

        if storable:
            if node_class is None:
                store = [
                    self.btn_store, self.data_format,
                    self.structure_description
                ]
            elif node_class not in self.DATA_FORMATS:
                raise ValueError(
                    "Unknown data format '{}'. Options: {}".format(
                        node_class, self.DATA_FORMATS))
            else:
                self.data_format.value = node_class
                store = [self.btn_store, self.structure_description]
        else:
            store = [self.structure_description]
        store = ipw.HBox(store)
        children = [self._structure_sources_tab, self.viewer, store]
        super(StructureUploadWidget, self).__init__(children=children,
                                                    **kwargs)

        self.file_upload.observe(self._on_file_upload, names='data')
        self.select_example.observe(self._on_select_example, names=['value'])
        self.btn_store.on_click(self._on_click_store)
        self.data_format.observe(self.reset_structure, names=['value'])
        self.structure_description.observe(self.reset_structure,
                                           names=['value'])

    @staticmethod
    def get_example_structures(examples):
        if not isinstance(examples, list):
            raise ValueError(
                "parameter examples should be of type list, {} given".format(
                    type(examples)))
        if examples:
            options = [("Select structure", False)]
            options += examples
            return options
        return []

    # pylint: disable=unused-argument
    def _on_file_upload(self, change):
        self.file_path = os.path.join(tempfile.mkdtemp(),
                                      self.file_upload.filename)
        with open(self.file_path, 'w') as f:
            f.write(self.file_upload.data)
        structure_ase = self.get_ase(self.file_path)
        self.select_structure(structure_ase=structure_ase,
                              name=self.file_upload.filename)

    def _on_select_example(self, change):
        if self.select_example.value:
            structure_ase = self.get_ase(self.select_example.value)
            self.file_path = self.select_example.value
        else:
            structure_ase = False
        self.select_structure(structure_ase=structure_ase,
                              name=self.select_example.label)

    def reset_structure(self, change=None):
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
        self.structure_description.value = self.get_description(
            structure_ase, name)
        self.structure_ase = structure_ase
        self.refresh_view()

    def get_ase(self, fname):
        try:
            traj = ase.io.read(fname, index=":")
        except Exception as exc:
            if exc.args:
                print(' '.join([str(c) for c in exc.args]))
            else:
                print("Unknown error")
            return False
        if not traj:
            print("Could not read any information from the file {}".format(
                fname))
            return False
        if len(traj) > 1:
            print(
                "Warning: Uploaded file {} contained more than one structure. I take the first one."
                .format(fname))
        return traj[0]

    def get_description(self, structure_ase, name):
        formula = structure_ase.get_chemical_formula()
        return "{} ({})".format(formula, name)

    def refresh_view(self):
        viewer = self.viewer
        # Note: viewer.clear() only removes the 1st component
        # pylint: disable=protected-access
        for comp_id in viewer._ngl_component_ids:
            viewer.remove_component(comp_id)
        if self.structure_ase is None:
            return
        viewer.add_component(nglview.ASEStructure(
            self.structure_ase))  # adds ball+stick
        viewer.add_unitcell()

    # pylint: disable=unused-argument
    def _on_click_store(self, change):
        self.store_structure()

    def store_structure(self, label=None, description=None):
        if self.frozen:
            return
        if self.structure_node is None:
            return
        if self.structure_node.is_stored:
            print("Already stored in AiiDA: " + repr(self.structure_node) +
                  " skipping..")
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
                    self._structure_node = CifData(file=os.path.abspath(
                        self.file_path),
                                                   scan_type='flex',
                                                   parse_policy='lazy')
                else:
                    from aiida.orm.nodes.data.cif import CifData
                    self._structure_node = CifData()
                    self._structure_node.set_ase(self.structure_ase)
            else:  # Target format is StructureData
                from aiida.orm import StructureData
                self._structure_node = StructureData(ase=self.structure_ase)
            self._structure_node.description = self.structure_description.value
            self._structure_node.label = os.path.splitext(self.name)[0]
        return self._structure_node
