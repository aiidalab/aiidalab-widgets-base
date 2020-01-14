"""Widgets to manage AiiDA export."""
import os
from ipywidgets import Button
from IPython.display import display


class ExportButtonWidget(Button):
    """Export Node button."""

    def __init__(self, process, **kwargs):
        self.process = process
        if 'description' not in kwargs:
            kwargs['description'] = "Export workflow ({})".format(self.process.id)
        if 'layout' not in kwargs:
            kwargs['layout'] = {}
        kwargs['layout']['width'] = 'initial'
        super(ExportButtonWidget, self).__init__(**kwargs)
        self.on_click(self.export_aiida_subgraph)

    def export_aiida_subgraph(self, change=None):  # pylint: disable=unused-argument
        """Perform export when the button is pressed"""
        import base64
        import subprocess
        from tempfile import mkdtemp
        from IPython.display import Javascript
        fname = os.path.join(mkdtemp(), 'export.aiida')
        subprocess.call(['verdi', 'export', 'create', fname, '-N', str(self.process.id)])
        with open(fname, 'rb') as fobj:
            b64 = base64.b64encode(fobj.read())
            payload = b64.decode()
        javas = Javascript("""
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload, filename='export_{}.aiida'.format(self.process.id)))
        display(javas)
