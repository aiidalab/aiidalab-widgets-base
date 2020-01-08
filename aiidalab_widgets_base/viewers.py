"""Jupyter viewers for AiiDA data objects."""

from __future__ import absolute_import
import base64

import ipywidgets as ipw
from six.moves import range
from IPython.display import display
import nglview

from .utils import find_ranges, string_range_to_set


def viewer(obj, downloadable=True, **kwargs):
    """Display AiiDA data types in Jupyter notebooks

    :param downloadable: If True, add link/button to download the content of displayed AiiDA object.
    :type downloadable: bool

    Returns the object itself if the viewer wasn't found."""
    import inspect
    import warnings
    from aiida.orm import Node

    if not (inspect.isclass(type(obj)) and issubclass(type(obj), Node)):  # only working with AiiDA nodes
        warnings.warn("This viewer works only with AiiDA objects, got {}".format(type(obj)))
        return obj

    try:
        _viewer = AIIDA_VIEWER_MAPPING[obj.node_type]
        return _viewer(obj, downloadable=downloadable, **kwargs)
    except (KeyError) as exc:
        if obj.node_type in str(exc):
            warnings.warn("Did not find an appropriate viewer for the {} object. Returning the object "
                          "itself.".format(type(obj)))
            return obj
        raise exc


class DictViewer(ipw.HTML):
    """Viewer class for Dict object

    :param parameter: Dict object to be viewed
    :type parameter: Dict
    :param downloadable: If True, add link/button to download the content of the object
    :type downloadable: bool"""

    def __init__(self, parameter, downloadable=True, **kwargs):
        super().__init__(**kwargs)
        import pandas as pd
        # Here we are defining properties of 'df' class (specified while exporting pandas table into html).
        # Since the exported object is nothing more than HTML table, all 'standard' HTML table settings
        # can be applied to it as well.
        # For more information on how to controle the table appearance please visit:
        # https://css-tricks.com/complete-guide-table-element/
        self.value = '''
        <style>
            .df { border: none; }
            .df tbody tr:nth-child(odd) { background-color: #e5e7e9; }
            .df tbody tr:nth-child(odd):hover { background-color:   #f5b7b1; }
            .df tbody tr:nth-child(even):hover { background-color:  #f5b7b1; }
            .df tbody td { min-width: 300px; text-align: center; border: none }
            .df th { text-align: center; border: none;  border-bottom: 1px solid black;}
        </style>
        '''
        pd.set_option('max_colwidth', 40)
        dataf = pd.DataFrame([(key, value) for key, value in sorted(parameter.get_dict().items())],
                             columns=['Key', 'Value'])
        self.value += dataf.to_html(classes='df', index=False)  # specify that exported table belongs to 'df' class
        # this is used to setup table's appearance using CSS
        if downloadable:
            payload = base64.b64encode(dataf.to_csv(index=False).encode()).decode()
            fname = '{}.csv'.format(parameter.pk)
            to_add = """Download table in csv format: <a download="{filename}"
            href="data:text/csv;base64,{payload}" target="_blank">{title}</a>"""
            self.value += to_add.format(filename=fname, payload=payload, title=fname)


class StructureDataViewer(ipw.VBox):
    """Viewer class for structure object

    :param structure: structure object to be viewed
    :type structure: StructureData or CifData
    :param downloadable: If True, add link/button to download the content of the object
    :type downloadable: bool"""

    SELECTION_SIZE = 10

    def __init__(self, structure=None, downloadable=True, **kwargs):
        self._structure = None
        self._name = None
        self._viewer = nglview.NGLWidget()
        self._viewer.observe(self._on_atom_click, names='picked')
        self._viewer.stage.set_parameters(mouse_preset='pymol')
        self._viewer.layout = {'width': "65%"}
        self._viewer.handle_resize()

        layout = {"description_width": "initial", "width": "95%"}
        center_button = ipw.Button(description="Center", layout=layout)
        center_button.on_click(lambda c: self._viewer.center())

        # Choose background color.
        background_color = ipw.ColorPicker(description="Background", layout=layout)

        def change_background(change):  # Note: change this to lambda when switched to python3.8
            self._viewer.background = change['new']

        background_color.observe(change_background, names="value")
        background_color.value = 'white'

        # Make screenshot.
        screenshot = ipw.Button(description="Screenshot")
        screenshot.on_click(lambda c: self._viewer.download_image())

        # Selected atoms.
        self._selected_atoms = ipw.Textarea(description='Selected atoms:',
                                            value='',
                                            style={'description_width': 'initial'})
        self._selected_atoms.observe(self._apply_selection, names='value')
        self.wrong_syntax = ipw.HTML(
            value="""<i class="fa fa-times" style="color:red;font-size:2em;" ></i> wrong syntax""",
            layout={'visibility': 'hidden'})
        self._selection = set()
        copy_selection_to_clipboard = ipw.Button(description="Copy to clipboard")
        clear_selection = ipw.Button(description="Clear selection")
        clear_selection.on_click(self.clear_selection)

        def copy_to_clipboard(change=None):  # pylint:disable=unused-argument
            from IPython.display import Javascript
            javas = Javascript("""
               function copyStringToClipboard (str) {{
                   // Create new element
                   var el = document.createElement('textarea');
                   // Set value (string to be copied)
                   el.value = str;
                   // Set non-editable to avoid focus and move outside of view
                   el.setAttribute('readonly', '');
                   el.style = {{position: 'absolute', left: '-9999px'}};
                   document.body.appendChild(el);
                   // Select text inside element
                   el.select();
                   // Copy text to clipboard
                   document.execCommand('copy');
                   // Remove temporary element
                   document.body.removeChild(el);
                }}
                copyStringToClipboard("{selection}");
           """.format(selection=self.shortened_selection))  # for the moment works for Chrome,
            # but doesn't work for Firefox
            display(javas)

        copy_selection_to_clipboard.on_click(copy_to_clipboard)

        # Camera type.
        camera_type = ipw.ToggleButtons(options={
            'Orthographic': 'orthographic',
            'Perspective': 'perspective'
        },
                                        description='Camera type:',
                                        layout=layout,
                                        style={'button_width': '115.5px'},
                                        orientation='vertical')

        def change_camera(change):
            self._viewer.camera = change['new']

        camera_type.observe(change_camera, names="value")

        if structure:
            self.structure = structure

        children = [
            ipw.HBox([
                self._viewer,
                ipw.VBox(
                    [
                        center_button, background_color, screenshot, camera_type, self._selected_atoms,
                        self.wrong_syntax,
                        ipw.HBox([copy_selection_to_clipboard, clear_selection])
                    ],
                    layout={"width": "35%"},
                )
            ],
                     display='flex')
        ]
        if downloadable:
            self.file_format = ipw.Dropdown(
                options=[
                    'xyz',
                    'cif',
                ],
                description="File format:",
            )
            self.download_btn = ipw.Button(description="Download")
            self.download_btn.on_click(self.download)
            children.append(ipw.HBox([self.file_format, self.download_btn]))

        if 'children' in kwargs:
            children += kwargs.pop('children')

        super().__init__(children, **kwargs)

    def _on_atom_click(self, change=None):  # pylint:disable=unused-argument
        """Update selection when clicked on atom."""
        if 'atom1' not in self._viewer.picked.keys():
            return  # did not click on atom

        index = self._viewer.picked['atom1']['index']

        if index not in self._selection:
            self._selection.add(index)
        else:
            self._selection.discard(index)
        self._selected_atoms.value = self.shortened_selection

    def highlight_atoms(self, vis_list, color='red', size=0.2, opacity=0.6):
        if not hasattr(self._viewer, "component_0"):
            return
        self._viewer._remove_representations_by_name(repr_name='selected_atoms')  # pylint:disable=protected-access
        self._viewer.add_ball_and_stick(  # pylint:disable=no-member
            name="selected_atoms",
            selection=vis_list,
            color=color,
            aspectRatio=size,
            opacity=opacity)

    def _apply_selection(self, change=None):  # pylint:disable=unused-argument
        """Apply selection specified in the text area."""
        short_selection = change['new']
        self._selection, syntax_ok = string_range_to_set(short_selection)
        if syntax_ok:
            self.wrong_syntax.layout.visibility = 'hidden'
            self.highlight_atoms(self._selection, color='green', size=8, opacity=0.2)
        else:
            self.wrong_syntax.layout.visibility = 'visible'

    def clear_selection(self, change=None):  # pylint:disable=unused-argument
        self._viewer._remove_representations_by_name(repr_name='selected_atoms')  # pylint:disable=protected-access
        self._selection = set()
        self._selected_atoms.value = self.shortened_selection

    @property
    def shortened_selection(self):
        return " ".join([
            str(t) if isinstance(t, int) else "{}..{}".format(t[0], t[1]) for t in find_ranges(sorted(self._selection))
        ])

    @property
    def structure(self):
        """Returns ASE Atoms object."""
        return self._structure

    @structure.setter
    def structure(self, structure):
        """Set structure to view

        :param structure: Structure to be viewed
        :type structure: StructureData, CifData, Atoms (ASE)"""
        from aiida.orm import Node
        from ase import Atoms

        # Remove the current structure(s) from the viewer.
        for comp_id in self._viewer._ngl_component_ids:  # pylint: disable=protected-access
            self._viewer.remove_component(comp_id)

        # We keep the structure as ASE Atoms object. If the object is not ASE, we convert to it.
        if isinstance(structure, Atoms):
            self._structure = structure
            self._name = structure.get_chemical_formula()
        elif isinstance(structure, Node):
            self._structure = structure.get_ase()
            self._name = structure.id
        elif structure is None:
            self._structure = None
            self._name = None
            return  # if no structure provided, the rest of the code can be skipped
        else:
            raise ValueError("Unsupported type {}, structure must be one of the following types: "
                             "ASE Atoms object, AiiDA CifData or StructureData.")

        # Add new structure to the viewer.
        self._viewer.add_component(nglview.ASEStructure(self._structure))  # adds ball+stick
        self._viewer.add_unitcell()  # pylint: disable=no-member
        self.clear_selection()

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare a structure for downloading."""
        self._download(payload=self._prepare_payload(), filename=str(self._name) + '.' + self.file_format.value)

    @staticmethod
    def _download(payload, filename):
        """Download payload as a file named as filename."""
        from IPython.display import Javascript
        javas = Javascript("""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload, filename=filename))
        display(javas)

    def _prepare_payload(self, file_format=None):
        """Prepare binary information."""
        from tempfile import NamedTemporaryFile

        file_format = file_format if file_format else self.file_format.value
        tmp = NamedTemporaryFile()
        self._structure.write(tmp.name, format=file_format)
        with open(tmp.name, 'rb') as raw:
            return base64.b64encode(raw.read()).decode()

    @property
    def thumbnail(self):
        return self._prepare_payload(file_format='png')


class FolderDataViewer(ipw.VBox):
    """Viewer class for FolderData object

    :param folder: FolderData object to be viewed
    :type folder: FolderData
    :param downloadable: If True, add link/button to download the content of the selected file in the folder
    :type downloadable: bool"""

    def __init__(self, folder, downloadable=True, **kwargs):
        self._folder = folder
        self.files = ipw.Dropdown(
            options=[obj.name for obj in self._folder.list_objects()],
            description="Select file:",
        )
        self.text = ipw.Textarea(value="",
                                 description='File content:',
                                 layout={
                                     'width': "900px",
                                     'height': '300px'
                                 },
                                 disabled=False)
        self.change_file_view()
        self.files.observe(self.change_file_view, names='value')
        children = [self.files, self.text]
        if downloadable:
            self.download_btn = ipw.Button(description="Download")
            self.download_btn.on_click(self.download)
            children.append(self.download_btn)
        super().__init__(children, **kwargs)

    def change_file_view(self, change=None):  # pylint: disable=unused-argument
        with self._folder.open(self.files.value) as fobj:
            self.text.value = fobj.read()

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare for downloading."""
        from IPython.display import Javascript

        payload = base64.b64encode(self._folder.get_object_content(self.files.value).encode()).decode()
        javas = Javascript("""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload, filename=self.files.value))
        display(javas)


class BandsDataViewer(ipw.VBox):
    """Viewer class for BandsData object

    :param bands: BandsData object to be viewed
    :type bands: BandsData"""

    def __init__(self, bands, **kwargs):
        from bokeh.io import show, output_notebook
        from bokeh.models import Span
        from bokeh.plotting import figure
        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            plot_info = bands._get_bandplot_data(cartesian=True, join_symbol="|")  # pylint: disable=protected-access
            # Extract relevant data
            y_data = plot_info['y'].transpose().tolist()
            x_data = [plot_info['x'] for i in range(len(y_data))]
            labels = plot_info['labels']
            # Create the figure
            plot = figure(y_axis_label='Dispersion ({})'.format(bands.units))
            plot.multi_line(x_data, y_data, line_width=2, line_color='red')
            plot.xaxis.ticker = [l[0] for l in labels]
            # This trick was suggested here: https://github.com/bokeh/bokeh/issues/8166#issuecomment-426124290
            plot.xaxis.major_label_overrides = {int(l[0]) if l[0].is_integer() else l[0]: l[1] for l in labels}
            # Add vertical lines
            plot.renderers.extend(
                [Span(location=l[0], dimension='height', line_color='black', line_width=3) for l in labels])
            show(plot)
        children = [out]
        super().__init__(children, **kwargs)


AIIDA_VIEWER_MAPPING = {
    'data.dict.Dict.': DictViewer,
    'data.structure.StructureData.': StructureDataViewer,
    'data.cif.CifData.': StructureDataViewer,
    'data.folder.FolderData.': FolderDataViewer,
    'data.array.bands.BandsData.': BandsDataViewer,
}
