"""Jupyter visualisers for different types of data."""
from __future__ import print_function
from __future__ import absolute_import

import ipywidgets as ipw
from six.moves import range
from IPython.display import display


class DictVisualizer(ipw.HTML):
    """Visualizer class for ParameterData object"""

    def __init__(self, parameter, downloadable=True, **kwargs):
        super(DictVisualizer, self).__init__(**kwargs)
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
            import base64
            payload = base64.b64encode(dataf.to_csv(index=False).encode()).decode()
            fname = '{}.csv'.format(parameter.pk)
            to_add = """Download table in csv format: <a download="{filename}"
            href="data:text/csv;base64,{payload}" target="_blank">{title}</a>"""
            self.value += to_add.format(filename=fname, payload=payload, title=fname)


class StructureDataVisualizer(ipw.VBox):
    """Visualizer class for StructureData object"""

    def __init__(self, structure, downloadable=True, **kwargs):
        import nglview
        self._structure = structure
        viewer = nglview.NGLWidget()
        viewer.add_component(nglview.ASEStructure(self._structure.get_ase()))  # adds ball+stick
        viewer.add_unitcell()  # pylint: disable=no-member
        children = [viewer]
        if downloadable:
            self.file_format = ipw.Dropdown(
                options=['xyz', 'cif'],
                description="File format:",
            )
            self.download_btn = ipw.Button(description="Download")
            self.download_btn.on_click(self.download)
            children.append(ipw.HBox([self.file_format, self.download_btn]))
        super(StructureDataVisualizer, self).__init__(children, **kwargs)

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare a structure for downloading."""
        import base64
        from tempfile import TemporaryFile
        from IPython.display import Javascript

        # ASE has strange problems with format, this is why I used if-else here.
        if self.file_format.value == 'xyz':
            with TemporaryFile(mode='w+') as fobj:
                self._structure.get_ase().write(fobj, format=self.file_format.value)
                fobj.seek(0)
                b64 = base64.b64encode(fobj.read().encode())
                payload = b64.decode()
        elif self.file_format.value == 'cif':
            with TemporaryFile() as fobj:
                self._structure.get_ase().write(fobj, format=self.file_format.value)
                fobj.seek(0)
                b64 = base64.b64encode(fobj.read())
                payload = b64.decode()

        javas = Javascript("""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload, filename=str(self._structure.id) + '.' + self.file_format.value))
        display(javas)


class FolderDataVisualizer(ipw.VBox):
    """Visualizer class for FolderData object"""

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
        super(FolderDataVisualizer, self).__init__(children, **kwargs)

    def change_file_view(self, change=None):  # pylint: disable=unused-argument
        with self._folder.open(self.files.value) as fobj:
            self.text.value = fobj.read()

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare for downloading."""
        import base64
        from IPython.display import Javascript
        with self._folder.open(self.files.value) as fobj:
            b64 = base64.b64encode(fobj.read().encode())
            payload = b64.decode()
        javas = Javascript("""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload, filename=self.files.value))
        display(javas)


class BandsDataVisualizer(ipw.VBox):
    """Visualizer class for BandsData object"""

    def __init__(self, bands, **kwargs):
        from bokeh.io import show, output_notebook
        from bokeh.models import Span
        from bokeh.plotting import figure
        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            plot_info = bands._get_bandplot_data(  # pylint: disable=protected-access
                cartesian=True, join_symbol="|")
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
        super(BandsDataVisualizer, self).__init__(children, **kwargs)
