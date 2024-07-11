from aiidalab_widgets_base.utils.loaders import load_css_stylesheet


def test_load_css_stylesheet():
    """Test `load_css_stylesheet` function."""
    package = "aiidalab_widgets_base.static.styles"
    load_css_stylesheet(package=package, filename="global.css")
    load_css_stylesheet(package=package)
