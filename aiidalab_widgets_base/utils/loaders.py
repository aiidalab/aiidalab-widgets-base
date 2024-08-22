from __future__ import annotations

from importlib.resources import Package, files
from pathlib import Path

from IPython.display import Javascript, display


def load_css_stylesheet(
    package: Package | None = None,
    css_path: str | Path = "",
    filename: str = "",
):
    """Load a CSS stylesheet from a package and inject it into the DOM.

    Parameters
    ----------
    `package` : `Package`, optional
        The package where the CSS file is located.
    `css_path` : `str` | `Path`, optional
        The path to the folder where the CSS file is located.
    `filename` : `str`, optional
        The name of the CSS file to load.
        If not provided, all CSS files in the package/folder will be loaded.
    """
    if package:
        root = files(package)
        filenames = (
            [root / filename]
            if filename
            else [
                root / path.name
                for path in root.iterdir()
                if path.is_file() and path.name.endswith(".css")
            ]
        )
    elif css_path:
        path = Path(css_path)
        filenames = [path / filename] if filename else [*path.glob("*.css")]
    else:
        raise ValueError("Either `package` or `path` must be provided.")

    for fn in filenames:
        stylesheet = fn.read_text()
        display(
            Javascript(f"""
                var style = document.createElement('style');
                style.type = 'text/css';
                style.innerHTML = `{stylesheet}`;
                document.head.appendChild(style);
            """)
        )
