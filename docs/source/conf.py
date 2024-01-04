# pylint: disable=invalid-name

# -*- coding: utf-8 -*-
"""Sphinx configuration for aiidalab-widgets-base."""
import os
import subprocess
import sys
import time
from pathlib import Path


# Load the temp profile to make sure the docs build succeed even if the current
# default profile of the AiiDA installation is not configured.
def load_temp_profile():
    """Load the temp profile to make sure the docs build succeed even if the current
    default profile of the AiiDA installation is not configured.
    """
    from aiida import load_profile
    from aiida.manage.configuration import get_config
    from aiida.storage.sqlite_temp import SqliteTempBackend

    profile = load_profile(
        SqliteTempBackend.create_profile(
            "readthedocs",
            options={"warnings.development_version": False, "runner.poll.interval": 1},
            debug=False,
        ),
        allow_switch=True,
    )
    config = get_config()
    config.add_profile(profile)
    config.set_default_profile(profile.name)


load_temp_profile()

from aiidalab_widgets_base import __version__  # pylint: disable=wrong-import-position

# work around unpickleable functions
sys.path.append(str(Path(__file__).parent))
from ipywidgets_docs_utils import jupyterlab_markdown_heading

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

myst_heading_anchors = 4
myst_heading_slug_func = jupyterlab_markdown_heading

nb_ipywidgets_js = {
    "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.4/require.min.js": {
        "integrity": "sha256-Ae2Vz/4ePdIu6ZyI/5ZGsYnb+m0JlOmKPjt6XZ9JJkA=",
        "crossorigin": "anonymous",
    },
    "https://cdn.jsdelivr.net/npm/@jupyter-widgets/html-manager@*/dist/embed-amd.js": {
        "data-jupyter-widgets-cdn": "https://cdn.jsdelivr.net/npm/",
        "crossorigin": "anonymous",
    },
}

nb_execution_mode = "cache"

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
copyright = "{}, {}. All rights reserved".format(
    copyright_year_string, copyright_owners
)  # pylint: disable=redefined-builtin

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

    Symlinks example jupyter notebooks so that they can be
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
    source_dir = Path(__file__).resolve().parent
    apidoc_dir = source_dir / "apidoc"
    package_dir = source_dir.parent.parent / "aiidalab_widgets_base"

    symlink_example_notebooks(source_dir)

    # In #1139, they suggest the route below, but this ended up
    # calling sphinx-build, not sphinx-apidoc
    # from sphinx.apidoc import main
    # main([None, '-e', '-o', apidoc_dir, package_dir, '--force'])

    cmd_path = "sphinx-apidoc"
    if hasattr(sys, "real_prefix"):  # Check to see if we are in a virtualenv
        # If we are, assemble the path manually
        cmd_path = os.path.abspath(os.path.join(sys.prefix, "bin", "sphinx-apidoc"))

    options = [
        "-o",
        apidoc_dir,
        package_dir,
        "--private",
        "--force",
        "--no-toc",
    ]

    # See https://stackoverflow.com/a/30144019
    env = os.environ.copy()
    env[
        "SPHINX_APIDOC_OPTIONS"
    ] = "members,special-members,private-members,undoc-members,show-inheritance"
    subprocess.check_call([cmd_path] + options, env=env)


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
