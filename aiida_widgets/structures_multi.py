from __future__ import print_function

import ase.io
import ipywidgets as ipw
from ipywidgets import Layout
from IPython.display import clear_output
from fileupload import FileUploadWidget
import tarfile
import tempfile
import nglview


class MultiStructureUploadWidget(ipw.VBox):
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
        
        self.selection_slider = ipw.SelectionSlider(
            options=[None,],
            disabled=False,
            orientation='vertical',
            description='Select structure:',
            layout = Layout(width='50%'),
        )
        
        view = ipw.HBox([self.viewer, self.selection_slider])
        
        self.selection_slider.on_trait_change(self.change_structure, 'value')
        self.btn_store_all = ipw.Button(description='Store all in AiiDA', disabled=True)
        self.btn_store_selected = ipw.Button(description='Store selected', disabled=True)
        self.structure_label = ipw.Text(placeholder="Label (optional)")
        
        self.description = ipw.HTML("""
        <h1> Instructions </h1>

        <ol>
            <li> Create a tarball that contains all the structures you want to put in the database: </li>
            > tar -czf random_name.tar.gz struct1.cif struct2.cif
            <br>
            or
            <br>
            > tar -czf random_name.tar.gz \*.cif
            <li> Hit "Select tarball" button and chose the random_name.tar.gz. Then press Open </li>
            <li> After the previous step the button "Store structures" will be activated. Press it </li>
            <li> The list of apploaded CIF files will be shown </li>
            <li> If you need more files, start again from the step 1 or 2 </li>
        </ol>

        <font color='red'> Warning: do not put structures into a subfolder, as they will be ignored. Do exactly as it is described in the step 1. </font> 
        """)

        self.atoms = None
        self.structure_node_class = node_class
        self.structure_node = None
        self.structure_names = []
        if node_class is None:
            self.data_format = ipw.RadioButtons(
                options=['CifData', 'StructureData'], description='Data type:')
            store = ipw.HBox(
                [self.btn_store_all, self.data_format, self.structure_label, self.btn_store_selected])
        else:
            self.data_format = None
            store = ipw.HBox([self.btn_store_all, self.structure_label, self.btn_store_selected])

        children = [self.file_upload, self.description, self.output, view, store]

        super(MultiStructureUploadWidget, self).__init__(
            children=children, **kwargs)

        self.file_upload.observe(self._on_file_upload, names='data')
        self.btn_store_all.on_click(self._on_click_store_all)
        self.btn_store_selected.on_click(self._on_click_store_selected)

        from aiida import load_dbenv, is_dbenv_loaded
        from aiida.backends import settings
        if not is_dbenv_loaded():
            load_dbenv(profile=settings.AIIDADB_PROFILE)
    
    def change_structure(self):
        if self.selection_slider.value is None:
            pass
        else:
            self.select_structure(name=self.selection_slider.value)

    # pylint: disable=unused-argument
    def _on_file_upload(self, change):
        with self.output:
            clear_output()
            self.structure_names = []
            # download an archive and put its content into a file
            tarball = tempfile.NamedTemporaryFile(suffix=self.file_upload.filename)
            with open(tarball.name, 'w') as f:
                f.write(self.file_upload.data)
            self.tar_name = tarball.name

            # create a temporary folder where all the structure will be extracted
            self.tmp_folder = tempfile.mkdtemp()

            # open the downloaded archive and extract all the structures
            tar = tarfile.open(self.tar_name)
            for member in tar.getmembers():
                struct = tar.extractfile(member)
                # apend the name in a list
                self.structure_names.append(member.name)
                with open(self.tmp_folder+'/'+member.name, 'w') as f:
                    f.write(struct.read())
            tar.close()
            
            self.selection_slider.options = self.structure_names
            self.selection_slider.value = self.structure_names[0]
            self.select_structure(name = self.structure_names[0])

    def select_structure(self, name=None):
        self.tmp_file = self.tmp_folder + '/' + name
        traj = ase.io.read(self.tmp_file, index=":")
        if len(traj) > 1:
            print("Error: Uploaded file contained more than one structure")
        atoms = traj[0]
        formula = atoms.get_chemical_formula()
        self.structure_label.value = "{} ({})".format(
            formula, name)
        self.atoms = atoms
        self.refresh_view()
        self.btn_store_all.disabled = False
        self.btn_store_selected.disabled = False

    def refresh_view(self):
        viewer = self.viewer
        # Note: viewer.clear() only removes the 1st component
        # pylint: disable=protected-access
        for comp_id in viewer._ngl_component_ids:
            viewer.remove_component(comp_id)

        viewer.add_component(nglview.ASEStructure(
            self.atoms))  # adds ball+stick
        viewer.add_unitcell()

    # pylint: disable=unused-argument
    def _on_click_store_all(self, change):
        for filename in self.structure_names:
            self.store_structure(filename)

    # pylint: disable=unused-argument
    def _on_click_store_selected(self, change):
        self.store_structure(self.selection_slider.value)

    def store_structure(self, filename):
        self.select_structure(name=filename)
        if self.atoms is None:
            print("Upload a structure first!")
            return

        # determine data source
        if filename.endswith('.cif'):
            source_format = 'CIF'
        else:
            source_format = 'ASE'

        # determine target format
        if self.structure_node_class is None:
            target_format = self.data_format.value
        else:
            target_format = self.structure_node_class

        # perform conversion
        if target_format == 'CifData':
            if source_format == 'CIF':
                from aiida.orm.data.cif import CifData
                structure_node = CifData(
                    file=self.tmp_file,
                    scan_type='flex',
                    parse_policy='lazy')
            else:
                from aiida.orm.data.cif import CifData
                structure_node = CifData()
                structure_node.set_ase(self.atoms)
        else:
            # Target format is StructureData
            from aiida.orm.data.structure import StructureData
            structure_node = StructureData(ase=self.atoms)

            #TODO: Figure out whether this is still necessary for structuredata
            # ensure that tags got correctly translated into kinds
            for t1, k in zip(self.atoms.get_tags(),
                             structure_node.get_site_kindnames()):
                t2 = int(k[-1]) if k[-1].isnumeric() else 0
                assert t1 == t2

        structure_node.description = self.structure_label.value
        structure_node.store()
        self.structure_node = structure_node
        print("Stored in AiiDA: " + repr(structure_node))