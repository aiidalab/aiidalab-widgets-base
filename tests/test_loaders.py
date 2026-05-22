from pathlib import Path

from aiidalab_widgets_base.loaders import LoadingWidget
from aiidalab_widgets_base.utils.loaders import load_css


def test_load_css():
    """Test `load_css` utility."""
    css_dir = Path("aiidalab_widgets_base/static/styles")
    load_css(css_path=css_dir)
    load_css(css_path=css_dir / "global.css")


def test_loading_widget():
    """Test `LoadingWidget`."""
    widget = LoadingWidget(message="Loading some widget")
    assert widget.message.value == "Loading some widget"
    assert widget.children[0].value == "Loading some widget"
    assert widget.children[1].value == "<i class='fa fa-spinner fa-spin fa-2x fa-fw'/>"
    assert "loading" in widget._dom_classes
