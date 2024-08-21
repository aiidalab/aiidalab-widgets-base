from __future__ import annotations

from pathlib import Path

from IPython.display import Javascript, display


def load_css(css_path: Path | str) -> None:
    """Load and inject CSS stylesheets into the DOM.

    Parameters
    ----------
    `css_path` : `Path` | `str`
        The path to the CSS stylesheet. If the path is a directory,
        all CSS files in the directory will be loaded.
    """
    path = Path(css_path)

    if not path.exists():
        raise FileNotFoundError(f"CSS file or directory not found: {path}")

    filenames = [*path.glob("*.css")] if path.is_dir() else [path]

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
