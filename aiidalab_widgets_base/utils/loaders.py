from importlib.resources import Package, files

from IPython.display import Javascript, display


def load_css_stylesheet(package: Package, filename: str = ""):
    """Load a CSS stylesheet from a package and inject it into the DOM.

    Parameters
    ----------
    `package` : `Package`
        The package where the CSS file is located.
    `filename` : `str`, optional
        The name of the CSS file to load.
        If not provided, all CSS files in the package will be loaded.
    """
    root = files(package)

    if filename:
        filenames = [filename]
    else:
        filenames = [
            path.name
            for path in root.iterdir()
            if path.is_file() and path.name.endswith(".css")
        ]

    for fn in filenames:
        stylesheet = (root / fn).read_text()
        display(
            Javascript(f"""
                var style = document.createElement('style');
                style.type = 'text/css';
                style.innerHTML = `{stylesheet}`;
                document.head.appendChild(style);
            """)
        )
