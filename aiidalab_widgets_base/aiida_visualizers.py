from __future__ import print_function
import os

import ipywidgets as ipw

class ParameterDataVisualizer(ipw.HTML):
    """Visualizer class for ParameterData object"""
    def __init__(self, parameter, downloadable=True, **kwargs):
        super(ParameterDataVisualizer, self).__init__(**kwargs)
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
        df = pd.DataFrame([(key, value) for key, value
                           in sorted(parameter.get_dict().items())
                          ], columns=['Key', 'Value'])
        self.value += df.to_html(classes='df', index=False) # specify that exported table belongs to 'df' class
                                                            # this is used to setup table's appearance using CSS
        if downloadable:
            import base64
            payload = base64.b64encode(df.to_csv(index=False).encode()).decode()
            fname = '{}.csv'.format(parameter.pk)
            to_add = """Download table in csv format: <a download="{filename}"
            href="data:text/csv;base64,{payload}" target="_blank">{title}</a>"""
            self.value += to_add.format(filename=fname, payload=payload,title=fname)

class StructureDataVisualizer(ipw.VBox):
    """Visualizer class for StructureData object"""
    def __init__(self, structure, downloadable=True, **kwargs):
        import nglview
        self._structure = structure
        viewer = nglview.NGLWidget()
        viewer.add_component(nglview.ASEStructure(self._structure.get_ase()))  # adds ball+stick
        viewer.add_unitcell()
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

    def download(self, b=None):
        import base64
        from tempfile import TemporaryFile
        from IPython.display import Javascript
        with TemporaryFile() as fobj:
            self._structure.get_ase().write(fobj, format=self.file_format.value)
            fobj.seek(0)
            b64 = base64.b64encode(fobj.read())
            payload = b64.decode()
        js = Javascript(
            """
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload,filename=str(self._structure.id)+'.'+self.file_format.value)
        )
        display(js)

class FolderDataVisualizer(ipw.VBox):
    """Visualizer class for FolderData object"""
    def __init__(self, folder, downloadable=True, **kwargs):
        self._folder = folder
        self.files = ipw.Dropdown(
            options=self._folder.get_folder_list(),
            description="Select file:",
        )
        self.text = ipw.Textarea(
            value="",
            description='File content:',
            layout={'width':"900px", 'height':'300px'},
            disabled=False
        )
        self.change_file_view()
        self.files.observe(self.change_file_view, names='value')
        children = [self.files, self.text]
        if downloadable:
            self.download_btn = ipw.Button(description="Download")
            self.download_btn.on_click(self.download)
            children.append(self.download_btn)
        super(FolderDataVisualizer, self).__init__(children, **kwargs)

    def change_file_view(self, b=None):
        with open(self._folder.get_abs_path(self.files.value), "rb") as fobj:
            self.text.value = fobj.read()

    def download(self, b=None):
        import base64
        from IPython.display import Javascript
        with open(self._folder.get_abs_path(self.files.value), "rb") as fobj:
            b64 = base64.b64encode(fobj.read())
            payload = b64.decode()
        js = Javascript(
            """
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload,filename=self.files.value)
        )
        display(js)

class BandsDataVisualizer(ipw.VBox):
    """Visualizer class for BandsData object"""
    def __init__(self, bands, **kwargs):
        from bokeh.plotting import figure
        from bokeh.io import show, output_notebook
        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            plot_info = bands._get_bandplot_data(cartesian=True, join_symbol="|")
            y = plot_info['y'].transpose().tolist()
            x = [plot_info['x'] for i in range(len(y))]
            labels = plot_info['labels']
            p = figure(y_axis_label='Dispersion ({})'.format(bands.units))
            p.multi_line(x, y, line_width=2)
            p.xaxis.ticker = [l[0] for l in labels]
            p.xaxis.major_label_overrides = {int(l[0]) if l[0].is_integer() else l[0]:l[1] for l in labels}
            # int(l[0]) if l[0].is_integer() else l[0]
            # This trick was suggested here: https://github.com/bokeh/bokeh/issues/8166#issuecomment-426124290
            show(p)
        children = [out]
        super(BandsDataVisualizer, self).__init__(children, **kwargs)