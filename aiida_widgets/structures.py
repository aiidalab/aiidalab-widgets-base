from __future__ import print_function

import ase.io
import ipywidgets as ipw
from IPython.display import clear_output
from fileupload import FileUploadWidget
import tempfile
import nglview


class StructureUploadWidget(ipw.VBox):
    def __init__(self, text="Upload Structure", node_class=None, **kwargs):
        """ Upload a structure and store it in AiiDA database.

        :param text: Text to display before upload button
        :type text: str
        :param node_class: AiiDA node class for storing the structure.
            Possible values: 'StructureData', 'CifData' or None (let the user decide).
            Note: If your workflows require a specific node class, better fix it here.

        """

        self.file_upload = FileUploadWidget(text)
        self.output = ipw.Output()
        self.viewer = nglview.NGLWidget()

        self.btn_store = ipw.Button(description='Store in AiiDA', disabled=True)
        self.structure_description = ipw.Text(placeholder="Label (optional)")

        self.structure_ase = None
        self.structure_node = None
        self.data_format = ipw.RadioButtons(
            options=['StructureData', 'CifData'], description='Data type:')

        if node_class is None:
            store = ipw.HBox(
                [self.btn_store, self.data_format, self.structure_description])
        else:
            self.data_format.value = node_class
            store = ipw.HBox([self.btn_store, self.structure_description])

        children = [self.file_upload, self.output, self.viewer, store]

        super(StructureUploadWidget, self).__init__(
            children=children, **kwargs)

        self.file_upload.observe(self._on_file_upload, names='data')
        self.btn_store.on_click(self._on_click_store)

        from aiida import load_dbenv, is_dbenv_loaded
        from aiida.backends import settings
        if not is_dbenv_loaded():
            load_dbenv(profile=settings.AIIDADB_PROFILE)

    # pylint: disable=unused-argument
    def _on_file_upload(self, change):

        with self.output:
            clear_output()

            self.tmp_folder = tempfile.mkdtemp()
            tmp = self.tmp_folder + '/' + self.file_upload.filename
            with open(tmp, 'w') as f:
                f.write(self.file_upload.data)
            self.tmp_file = tmp

            self.select_structure(name=self.file_upload.filename)

    def select_structure(self, name=None):
        self.tmp_file = self.tmp_folder + '/' + name
        traj = ase.io.read(self.tmp_file, index=":")
        if len(traj) > 1:
            print("Warning: Uploaded file {} contained more than one structure. I take the first one.".format(name))
        structure_ase = traj[0]
        formula = structure_ase.get_chemical_formula()
        self.structure_description.value = "{} ({})".format(
            formula, name)
        self.structure_ase = structure_ase
        self.refresh_view()
        self.btn_store.disabled = False

    def refresh_view(self):
        viewer = self.viewer

        # Note: viewer.clear() only removes the 1st component
        # pylint: disable=protected-access
        for comp_id in viewer._ngl_component_ids:
            viewer.remove_component(comp_id)

        viewer.add_component(nglview.ASEStructure(
            self.structure_ase))  # adds ball+stick
        viewer.add_unitcell()
        #self.viewer.center()

    # pylint: disable=unused-argument
    def _on_click_store(self, change):
        self.store_structure(self.file_upload.filename)

    def store_structure(self, filename):
        if self.structure_ase is None:
            print("Upload a structure first!")
            return

        # determine data source
        if filename.endswith('.cif'):
            source_format = 'CIF'
        else:
            source_format = 'ASE'

        # perform conversion
        if self.data_format.value == 'CifData':
            if source_format == 'CIF':
                from aiida.orm.data.cif import CifData
                structure_node = CifData(
                    file=self.tmp_file,
                    scan_type='flex',
                    parse_policy='lazy')
            else:
                from aiida.orm.data.cif import CifData
                structure_node = CifData()
                structure_node.set_ase(self.structure_ase)
        else:
            # Target format is StructureData
            from aiida.orm.data.structure import StructureData
            structure_node = StructureData(ase=self.structure_ase)

            #TODO: Figure out whether this is still necessary for structuredata
            # ensure that tags got correctly translated into kinds
            for t1, k in zip(self.structure_ase.get_tags(),
                             structure_node.get_site_kindnames()):
                t2 = int(k[-1]) if k[-1].isnumeric() else 0
                assert t1 == t2

        structure_node.description = self.structure_description.value
        structure_node.label = ".".join(self.file_upload.filename.split('.')[:-1])
        structure_node.store()
        self.structure_node = structure_node

        print("Stored in AiiDA: " + repr(structure_node))
