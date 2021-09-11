************
Installation
************

The AiiDAlab widgets app comes pre-installed in the AiiDAlab environment.

The app contains
 * the `aiidalab-widgets-base` Python package that contains the widgets (`from aiidalab_widgets_base import ...`)
 * several Jupyter notebooks illustrating how to use the widgets

Installation outside the AiiDAlab
=================================

Install the Python package from PyPI:

.. code-block:: bash

    pip install aiidalab-widgets-base

For developers, clone the app and install the Python package in editable mode:

.. code-block:: bash

    git clone https://github.com/aiidalab/aiidalab-widgets-base.git
    cd aiidalab-widgets-base
    pip install -e .


Optional dependencies
---------------------

The `SmilesWidget` widget requires the `OpenBabel <http://openbabel.org/>`_ library.
