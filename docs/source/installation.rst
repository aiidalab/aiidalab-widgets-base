************
Installation
************

The AiiDAlab widgets are already pre-installed in the AiiDAlab environment.

This includes:

 * the ``aiidalab-widgets-base`` Python package that contains the widgets (``from aiidalab_widgets_base import ...``)
 * the "AiiDAlab Widgets" app that contains Jupyter notebooks illustrating how to use the widgets

Installation outside the AiiDAlab
=================================

Install the Python package from PyPI:

.. code-block:: bash

    pip install aiidalab-widgets-base

Developers may want to clone the git repository containing the app and the notebooks and install the Python package in editable mode:

.. code-block:: bash

    git clone https://github.com/aiidalab/aiidalab-widgets-base.git
    cd aiidalab-widgets-base
    pip install -e .


Optional dependencies
---------------------

The `SmilesWidget` widget requires the `OpenBabel <http://openbabel.org/>`_ library.
