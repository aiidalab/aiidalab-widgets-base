from __future__ import print_function

import ase.io
import ipywidgets as ipw
from IPython.display import clear_output
from fileupload import FileUploadWidget
from tempfile import NamedTemporaryFile

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

        self.btn_store = ipw.Button(description='Store in AiiDA', disable=True)
        self.structure_label = ipw.Text(placeholder="Label (optional)")

        self.node_class = node_class
        self.atoms = None
        if node_class is None:
            self.data_format = ipw.RadioButtons(
                options=['CifData', 'StructureData'], description='Data type:')
            store = ipw.HBox(
                [self.btn_store, self.data_format, self.structure_label])
        else:
            self.data_format = None
            store = ipw.HBox([self.btn_store, self.structure_label])

        children = [self.file_upload, self.output, self.viewer, store]

        super(StructureUploadWidget, self).__init__(
            children=children, **kwargs)

        self.file_upload.observe(self._on_file_upload, names='data')
        #self.observe(self._update_children, names='value')
        self.btn_store.on_click(self._on_click_store)

        from aiida import load_dbenv, is_dbenv_loaded
        from aiida.backends import settings
        if not is_dbenv_loaded():
            load_dbenv(profile=settings.AIIDADB_PROFILE)

    # pylint: disable=unused-argument
    def _on_file_upload(self, change):

        with self.output:
            clear_output()

            tmp = NamedTemporaryFile(suffix=self.file_upload.filename)
            with open(tmp.name, 'w') as f:
                f.write(self.file_upload.data)
            self.tmp_file = tmp

            traj = ase.io.read(tmp.name, index=":")
            if len(traj) > 1:
                print("Error: Uploaded file contained more than one structure")
            atoms = traj[0]
            formula = atoms.get_chemical_formula()
            self.structure_label.value = "{} ({})".format(
                formula, self.file_upload.filename)
            self.atoms = atoms
            self.refresh_view()
            self.btn_store.disabled = False

    def refresh_view(self):
        self.viewer.add_component(nglview.ASEStructure(
            self.atoms))  # adds ball+stick
        self.viewer.add_unitcell()
        self.viewer.center()

    # pylint: disable=unused-argument
    def _on_click_store(self, change):

        filename = self.file_upload.filename

        if filename is None:
            print("Upload a structure first!")
            return

        # determine data source
        if filename.endswith('.cif'):
            source_format = 'CIF'
        else:
            source_format = 'ASE'

        # determine target format
        if self.node_class is None:
            target_format = self.data_format.value
        else:
            target_format = self.node_class

        # perform conversion
        if target_format == 'CifData':
            if source_format == 'CIF':
                from aiida.orm.data.cif import CifData
                atoms_node = CifData(
                    file=self.tmp_file.name,
                    scan_type='flex',
                    parse_policy='lazy')
            else:
                from aiida.orm.data.cif import cif_from_ase
                atoms_node = cif_from_ase(self.atoms)
        else:
            # Target format is StructureData
            from aiida.orm.data.structure import StructureData
            atoms_node = StructureData(ase=self.atoms)

            #TODO: Figure out whether this is still necessary for structuredata
            # ensure that tags got correctly translated into kinds
            for t1, k in zip(self.atoms.get_tags(),
                             atoms_node.get_site_kindnames()):
                t2 = int(k[-1]) if k[-1].isnumeric() else 0
                assert t1 == t2

        atoms_node.description = self.structure_label.value
        atoms_node.store()

        print("Stored in AiiDA: " + repr(atoms_node))
