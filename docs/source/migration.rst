*********
Migration
*********

This page lists breaking changes between releases and what to do about them.
Purely additive changes (new widgets, new parameters) are not listed here -- see the `CHANGELOG <https://github.com/aiidalab/aiidalab-widgets-base/blob/master/CHANGELOG.md>`_ for the full list of changes.

2.5.x to 3.0
============

Version 3.0 removes a number of legacy widgets and updates minimum supported python version to 3.12 and ipywidgets dependency to v8. Number of other dependencies have been also updated as listed below.
This section lists the changes that can break code written against ``aiidalab-widgets-base`` 2.5.x, and what to do about each of them.

Updated minimum dependency versions
------------------------------------

* **Python**: the minimum supported version is now 3.12 (was 3.9).
  Python 3.9, 3.10 and 3.11 are no longer supported
  (`#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).
* **aiida-core**: the minimum supported version is now ``2.8`` (was ``2.2``)
  (`#730 <https://github.com/aiidalab/aiidalab-widgets-base/pull/730>`__, `#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).
* **spglib**: only spglib ``>=2.5`` is supported; spglib 1.x no longer works
* **ase**: the minimum supported version is now ``3.23`` (was ``3.18``)
  (`#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).
* **rdkit** (``smiles`` extra): the minimum supported version is now ``2024.9.6`` (was ``2021.09.2``)
  (`#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).

Update your own package's dependency constraints accordingly before upgrading.

``ipywidgets`` 8 is now required
----------------------------------

The package now depends on ``ipywidgets~=8.1`` (was ``~=7.7``)
(`#725 <https://github.com/aiidalab/aiidalab-widgets-base/pull/725>`__).
This is the change most likely to require code changes downstream -- see `ipywidgets' migration guide <https://ipywidgets.readthedocs.io/en/8.1.0/migration_guides.html#migrating-from-7-x-to-8-0>`_ for the full list of changes (e.g. ``FileUpload.value`` changed shape, ``Accordion``'s default ``selected_index`` changed from ``0`` to ``None``).

``WizardAppWidget`` gained an ``open_first_step`` parameter (default ``True``), which was added specifically to preserve the pre-3.0 behavior (first step expanded on load) after the ``ipywidgets`` 8 change above.
No action is required unless you want the wizard to start fully collapsed, in which case pass ``open_first_step=False``
(`#792 <https://github.com/aiidalab/aiidalab-widgets-base/pull/792>`__).

Widgets removed
----------------

``ElnConfigureWidget``, ``ElnExportWidget``, ``ElnImportWidget``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All ELN-related widgets and the ``elns.py`` module have moved to the `aiidalab-eln <https://github.com/aiidalab/aiidalab-eln>`_ package, and the ``eln`` extra (``pip install aiidalab-widgets-base[eln]``) no longer exists
(`#774 <https://github.com/aiidalab/aiidalab-widgets-base/pull/774>`__).

.. code-block:: bash

    pip install aiidalab-eln

.. code-block:: python

    # Before
    from aiidalab_widgets_base import ElnConfigureWidget, ElnExportWidget, ElnImportWidget

    # After
    from aiidalab_eln import ElnConfigureWidget, ElnExportWidget, ElnImportWidget

``OpenAiidaNodeInAppWidget``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Removed with no replacement, along with the runtime dependency on the ``aiidalab`` package itself (this package no longer requires ``aiidalab`` to be installed)
(`#761 <https://github.com/aiidalab/aiidalab-widgets-base/pull/761>`__).

``BandsDataViewer``
^^^^^^^^^^^^^^^^^^^^^^

Removed along with the ``bokeh`` dependency.
``viewer(node)`` no longer renders an interactive band-structure plot for ``BandsData`` nodes -- it now falls back to the generic/no-op behavior for node types without a registered viewer.
You might find a more advanced alternative in the `BandsPdosPlotly <https://github.com/aiidalab/aiidalab-qe/tree/main/src/aiidalab_qe/common/bands_pdos>`_ widget in QeApp
(`#734 <https://github.com/aiidalab/aiidalab-widgets-base/pull/734>`__).


``ipw.Output``-based widgets replaced with ``ipw.VBox``/``ipw.HTML``
-------------------------------------------------------------------------

``ipw.Output`` has a history of display bugs in AiiDAlab, so it has been replaced across the codebase.
Two public APIs are affected:

* **``install_create_github_issue_exception_handler(output, ...)``** now expects ``output`` to be a widget with a ``.children`` attribute (e.g. ``ipw.VBox``), not an ``ipw.Output``
  (`#798 <https://github.com/aiidalab/aiidalab-widgets-base/pull/798>`__):

  .. code-block:: python

      # Before
      output = ipw.Output()
      install_create_github_issue_exception_handler(output, url=...)
      with output:
          display(welcome_message, app_with_work_chain_selector, footer)

      # After
      output = ipw.VBox()
      install_create_github_issue_exception_handler(output, url=...)
      output.children = [welcome_message, app_with_work_chain_selector, footer]
