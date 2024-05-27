"""Widgets to manage AiiDA export."""

import os

import ipywidgets as ipw


class ExportButtonWidget(ipw.Button):
    """Export Node button."""

    def __init__(self, process, **kwargs):
        self.process = process
        if "description" not in kwargs:
            kwargs["description"] = f"Export workflow ({self.process.pk})"
        if "layout" not in kwargs:
            kwargs["layout"] = {}
        kwargs["layout"]["width"] = "initial"
        super().__init__(**kwargs)
        self.on_click(self.export_aiida_subgraph)

    def export_aiida_subgraph(self, change=None):  # pylint: disable=unused-argument
        """Perform export when the button is pressed"""
        import base64
        import subprocess
        import tempfile

        from IPython.display import Javascript, display

        fname = os.path.join(tempfile.mkdtemp(), "export.aiida")
        subprocess.call(
            ["verdi", "archive", "create", fname, "-N", str(self.process.pk)]
        )
        with open(fname, "rb") as fobj:
            b64 = base64.b64encode(fobj.read())
            payload = b64.decode()
        javas = Javascript(
            """
            var link = document.createElement('a');
            link.href = "data:;base64,{payload}"
            link.download = "{filename}"
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """.format(payload=payload, filename=f"export_{self.process.pk}.aiida")
        )
        display(javas)
