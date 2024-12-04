from pathlib import Path

from aiidalab_widgets_base.utils.loaders import load_css


def test_load_css():
    """Test `load_css` utility."""
    css_dir = Path("aiidalab_widgets_base/static/styles")
    load_css(css_path=css_dir)
    load_css(css_path=css_dir / "global.css")
