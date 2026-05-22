"""Sphinx configuration for aiidalab-widgets-base."""

import time
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore", category=UserWarning, message="Creating AiiDA configuration folder .*"
)

from aiidalab_widgets_base import __version__

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.mathjax",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_nb",
]

nb_execution_mode = "off"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = ".rst"

# The master toctree document.
# ~ master_doc = 'index'
master_doc = "index"

# General information about the project.
project = "aiidalab-widgets-base"
copyright_first_year = "2020"
copyright_owners = "The AiiDAlab Team"

current_year = str(time.localtime().tm_year)
copyright_year_string = (
    current_year
    if current_year == copyright_first_year
    else f"{copyright_first_year}-{current_year}"
)
copyright = f"{copyright_year_string}, {copyright_owners}. All rights reserved"  # noqa

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The full version, including alpha/beta/rc tags.
# The short X.Y version.
version = ".".join(__version__.split(".")[:2])

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
show_authors = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# Output file base name for HTML help builder.
htmlhelp_basename = "aiidalab-widgets-base-doc"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

html_theme = "pydata_sphinx_theme"

# The pydata-sphinx-theme already loads the bootstrap css.
panels_add_bootstrap_css = False

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = "_static/aiidalab_logo.png"


html_theme_options = {
    "navigation_with_keys": True,
}

# -- Modifications for Readthedocs ----------------------------------------


def symlink_example_notebooks(source_dir: Path):
    """Symlink example Jupyter notebooks.

    Symlinks example Jupyter notebooks so that they can be
    included into the documentation.
    """
    notebooks_dir = source_dir.parent.parent / "notebooks"
    target_dir = source_dir / "widget-list" / "notebooks"
    if not target_dir.exists():
        target_dir.symlink_to(notebooks_dir, target_is_directory=True)


def run_apidoc(_):
    """Runs sphinx-apidoc when building the documentation.
    Needs to be done in conf.py in order to include the APIdoc in the
    build on readthedocs.
    See also https://github.com/rtfd/readthedocs.org/issues/1139
    """
    # https://github.com/readthedocs/readthedocs.org/issues/1139#issuecomment-715284488
    from sphinx.ext.apidoc import main

    source_dir = Path(__file__).resolve().parent
    apidoc_dir = source_dir / "apidoc"
    package_dir = source_dir.parent.parent / "aiidalab_widgets_base"

    symlink_example_notebooks(source_dir)

    options = [
        "--force",
        "--no-toc",
        "-o",
        str(apidoc_dir),
        str(package_dir),
    ]
    main(options)


def setup(app):
    app.connect("builder-inited", run_apidoc)


# Warnings to ignore when using the -n (nitpicky) option
# We should ignore any python built-in exception, for instance
nitpick_ignore = []
for line in open("nitpick-exceptions"):
    if line.strip() == "" or line.startswith("#"):
        continue
    dtype, target = line.split(None, 1)
    target = target.strip()
    nitpick_ignore.append((dtype, target))
