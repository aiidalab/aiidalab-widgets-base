"""Jupyter visualisers for different types of data."""
from __future__ import print_function
from __future__ import absolute_import

import ipywidgets as ipw
from six.moves import range
from IPython.display import display
import nglview


def viewer(obj, downloadable=True, **kwargs):
    """Display AiiDA data types in Jupyter notebooks.

    :param downloadable: If True, add link/button to download content of displayed AiiDA object.

    Defers to IPython.display.display for any objects it does not recognize."""

    try:
        visualizer = AIIDA_VISUALIZER_MAPPING[obj.node_type]
        return visualizer(obj, downloadable=downloadable, **kwargs)
    except (AttributeError, KeyError):
        return obj


class DictVisualizer(ipw.HTML):
    """Visualizer class for ParameterData object."""

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
    """Visualizer class for StructureData object."""

    def __init__(self, structure, downloadable=True, **kwargs):
        self._structure = structure
        self.viewer = nglview.NGLWidget()
        self.refresh_view()
        children = [self.viewer]
        if downloadable:
            self.file_format = ipw.Dropdown(
                options=['xyz', 'cif', 'png'],
                description="File format:",
            )
            self.download_btn = ipw.Button(description="Download")
            self.download_btn.on_click(self.download)
            children.append(ipw.HBox([self.file_format, self.download_btn]))
        super(StructureDataVisualizer, self).__init__(children, **kwargs)

    def update_structure(self, structure):
        """Update structure."""
        self._structure = structure
        self.refresh_view()

    def refresh_view(self):
        """Reset the structure view."""
        # Note: viewer.clear() only removes the 1st component
        # pylint: disable=protected-access
        for comp_id in self.viewer._ngl_component_ids:
            self.viewer.remove_component(comp_id)
        self.viewer.add_component(nglview.ASEStructure(self._structure.get_ase()))  # adds ball+stick
        self.viewer.add_unitcell()  # pylint: disable=no-member

    def download(self, change=None):  # pylint: disable=unused-argument
        """Prepare a structure for downloading."""
        from IPython.display import Javascript

        javas = Javascript("""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=self._prepare_payload(),
                       filename=str(self._structure.id) + '.' + self.file_format.value))
        display(javas)

    def _prepare_payload(self, file_format=None):
        """Prepare binary information."""
        import base64
        from tempfile import NamedTemporaryFile

        file_format = file_format if file_format else self.file_format.value
        tmp = NamedTemporaryFile()
        self._structure.get_ase().write(tmp.name, format=file_format)
        with open(tmp.name, 'rb') as raw:
            return base64.b64encode(raw.read()).decode()

    @property
    def thumbnail(self):
        return self._prepare_payload(file_format='png')


class TrajectoryDataVisualizer(ipw.VBox):
    """Visualizer class for TrajectoryData object."""

    def __init__(self, trajectory, downloadable=True, **kwargs):
        from bokeh.io import show, output_notebook
        from bokeh.models import ColumnDataSource
        from bokeh.plotting import figure

        # TrajectoryData object from AiiDA
        self._trajectory = trajectory

        # Bokeh data objects containing the info to plot lines and selected trajectory points
        self._bokeh_plot_line = ColumnDataSource(data=dict(x=[], y=[]))
        self._bokeh_plot_circle = ColumnDataSource(data=dict(x=[], y=[]))

        # Bokeh plot
        self._bokeh_plot = figure()

        # Inserting data into the plot
        self._bokeh_plot.line('x', 'y', source=self._bokeh_plot_line, line_width=2, line_color='red')
        self._bokeh_plot.circle('x', 'y', source=self._bokeh_plot_circle, radius=0.05, line_alpha=0.6)

        # Trajectory navigator
        self._step_selector = ipw.IntSlider(
            value=2,
            min=self._trajectory.get_stepids()[0],
            max=self._trajectory.get_stepids()[-1],
        )
        self._step_selector.observe(self.update, names="value")

        # Property to plot
        self._property_selector = ipw.Dropdown(
            options=trajectory.get_arraynames(),
            value='energy_ewald',
            description="Value to plot:",
        )
        self._property_selector.observe(self.update, names="value")

        self._viewer = StructureDataVisualizer(trajectory.get_step_structure(self._step_selector.value),
                                               downloadable=downloadable)
        self._bokeh_plot_circle.data = dict(
            x=[self._step_selector.value],
            y=[self._trajectory.get_array(self._property_selector.value)[self._step_selector.value]])
        self._plot = ipw.Output()
        children = [
            ipw.HBox([self._viewer, ipw.VBox([self._plot, self._property_selector])]),
            self._step_selector,
        ]
        self.update()
        output_notebook(hide_banner=True)
        with self._plot:
            show(self._bokeh_plot)
        super(TrajectoryDataVisualizer, self).__init__(children, **kwargs)

    def update(self, change=None):  # pylint: disable=unused-argument
        """Update the data plot."""
        self._viewer.update_structure(self._trajectory.get_step_structure(self._step_selector.value))
        print("data1", [self._step_selector.value])
        print("data2", [self._trajectory.get_array(self._property_selector.value)[self._step_selector.value]])
        self._bokeh_plot_circle.data = dict(
            x=[self._step_selector.value],
            y=[self._trajectory.get_array(self._property_selector.value)[self._step_selector.value]])
        x_data = self._trajectory.get_stepids()
        self._bokeh_plot_line.data = dict(x=x_data,
                                          y=self._trajectory.get_array(self._property_selector.value)[:len(x_data)])


class FolderDataVisualizer(ipw.VBox):
    """Visualizer class for FolderData object."""

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

        payload = base64.b64encode(self._folder.get_object_content(self.files.value)).decode()
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


AIIDA_VISUALIZER_MAPPING = {
    'data.dict.Dict.': DictVisualizer,
    'data.structure.StructureData.': StructureDataVisualizer,
    'data.cif.CifData.': StructureDataVisualizer,
    'data.folder.FolderData.': FolderDataVisualizer,
    'data.array.bands.BandsData.': BandsDataVisualizer,
    'data.array.trajectory.TrajectoryData.': TrajectoryDataVisualizer,
}
