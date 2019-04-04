from __future__ import print_function
import os

import ipywidgets as ipw
from aiida import load_dbenv, is_dbenv_loaded
from aiida.backends import settings
if not is_dbenv_loaded():
    load_dbenv(profile=settings.AIIDADB_PROFILE)

class ParameterDataVisualizer(ipw.HTML):
    """Basic visualizer class for ParameterData object"""
    def __init__(self, parameter, **kwargs):
        import pandas as pd
        import base64
        from IPython.display import FileLink
        df = pd.DataFrame([(key, value) for key, value in parameter.get_dict().items()], columns=['key', 'value'])
        self.value = df.to_html(index=False)
        payload = base64.b64encode(df.to_csv().encode()).decode()
        fname = '{}.csv'.format(parameter.pk)
        self.value += """<a download="{filename}" href="data:text/csv;base64,{payload}" target="_blank">{title}</a>"""
        self.value = self.value.format(filename=fname, payload=payload,title=fname)
        super(ParameterDataVisualizer, self).__init__(**kwargs)

class StructureDataVisualizer(ipw.VBox):
    """Basic visualizer class for StructureData object"""
    def __init__(self, structure, **kwargs):
        import nglview
        viewer = nglview.NGLWidget()
        viewer.add_component(nglview.ASEStructure(structure.get_ase()))  # adds ball+stick
        viewer.add_unitcell()
        children = [viewer]
        super(StructureDataVisualizer, self).__init__(children, **kwargs)

class FolderDataVisualizer(ipw.HBox):
    """Basic visualizer class for FolderData object"""
    def __init__(self, folder, **kwargs):
        self._folder = folder
        self.files = ipw.Dropdown(
            options=self._folder.get_folder_list(),
            description="Select file:",
        )
        self.download_btn = ipw.Button(description="Download")
        self.download_btn.on_click(self.download)
        children = [self.files, self.download_btn]
        super(FolderDataVisualizer, self).__init__(children, **kwargs)

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
