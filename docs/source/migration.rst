*********
Migration
*********

This page lists breaking changes between releases and what to do about them.
Purely additive changes (new widgets, new parameters) are not listed here — see the `CHANGELOG <https://github.com/aiidalab/aiidalab-widgets-base/blob/master/CHANGELOG.md>`_ for the full list of changes.

2.5.x to 3.0
============

Version 3.0 removes a number of legacy widgets and tightens the package's dependency floors.
This section lists the changes that can break code written against ``aiidalab-widgets-base`` 2.5.x, and what to do about each of them.

Dependency floors raised
-------------------------

* **Python**: the minimum supported version is now 3.12 (was 3.9).
  Python 3.9, 3.10 and 3.11 are no longer supported
  (`#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).
* **aiida-core**: the minimum supported version is now ``2.8`` (was ``2.2``)
  (`#730 <https://github.com/aiidalab/aiidalab-widgets-base/pull/730>`__, `#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).
* **spglib**: only spglib ``>=2.5`` is supported; spglib 1.x no longer works
  (``BasicCellEditor``'s "standardize cell" action relies on the spglib 2.x dataclass-based interface)
  (`#791 <https://github.com/aiidalab/aiidalab-widgets-base/pull/791>`__).
* **ase**: the minimum supported version is now ``3.23`` (was ``3.18``)
  (`#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).
* **rdkit** (``smiles`` extra): the minimum supported version is now ``2024.9.6`` (was ``2021.09.2``)
  (`#809 <https://github.com/aiidalab/aiidalab-widgets-base/pull/809>`__).

Update your own package's dependency constraints accordingly before upgrading.

``ipywidgets`` 8 is now required
----------------------------------

The package now depends on ``ipywidgets~=8.1`` (was ``~=7.7``), and the ``widgetsnbextension`` pin has been dropped
(`#725 <https://github.com/aiidalab/aiidalab-widgets-base/pull/725>`__).
This is the change most likely to require code changes downstream:

* **``FileUpload.value`` changed shape.**
  In ipywidgets 7 it was a ``dict`` keyed by filename; in ipywidgets 8 it is a ``tuple`` of dicts, each with ``name``/``content`` keys.
  If your code reads ``StructureUploadWidget.file_upload.value`` (or any other ``FileUpload`` widget) directly, update it, e.g.:

  .. code-block:: python

      # Before (ipywidgets 7)
      for fname, item in change["new"].items():
          content = item["content"]

      # After (ipywidgets 8)
      for item in change["new"]:
          fname, content = item["name"], item["content"]

* **``ipw.Accordion``'s default ``selected_index`` changed from ``0`` to ``None``.**
  Any accordion you build yourself (including subclasses that compose ``WizardAppWidgetStep``\ s) now opens fully collapsed unless you pass ``selected_index`` explicitly.
  ``WizardAppWidget`` itself keeps the old behavior by default (see below), but custom accordions do not.
* More generally, review any code that relies on ipywidgets 7-specific APIs
  (e.g. ``set_title(index, title)`` on ``Accordion``/``Tab``, which still works but is deprecated in favor of the ``titles=`` constructor argument).

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
``viewer(node)`` no longer renders an interactive band-structure plot for ``BandsData`` nodes — it now falls back to the generic/no-op behavior for node types without a registered viewer.
If you need band-structure plotting, use another plotting library directly (e.g. matplotlib) or a downstream app's own viewer
(`#734 <https://github.com/aiidalab/aiidalab-widgets-base/pull/734>`__).

``pandas`` is no longer a dependency
--------------------------------------

``DictViewer`` used to build its HTML table via ``pandas``; it now uses a small built-in HTML renderer with equivalent output.
If your code (or environment pinning) relied on ``aiidalab-widgets-base`` pulling in ``pandas`` transitively, add ``pandas`` to your own dependencies explicitly
(`#737 <https://github.com/aiidalab/aiidalab-widgets-base/pull/737>`__).

``ipw.Output``-based widgets replaced with ``ipw.VBox``/``ipw.HTML``
-------------------------------------------------------------------------

``ipw.Output`` has a history of display bugs in AiiDAlab, so it has been replaced across the codebase.
Two public APIs are affected:

* **``NodesTreeWidget``** is now a subclass of ``ipw.VBox`` instead of ``ipw.Output``.
  Code that used it as an output context manager (e.g. ``with tree_widget: display(...)``) or otherwise relied on ``Output`` behavior needs to be updated to work with ``VBox``/``.children`` instead
  (`#797 <https://github.com/aiidalab/aiidalab-widgets-base/pull/797>`__).
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

Custom exceptions removed
---------------------------

The ``aiidalab_widgets_base.utils.exceptions`` module has been removed entirely.

* ``ListOrTuppleError`` no longer exists.
  ``StructureManagerWidget`` (and other code that used to raise it) now raises a plain ``TypeError`` with an equivalent message.
  Since ``ListOrTuppleError`` was itself a ``TypeError`` subclass, code that catches ``TypeError`` is unaffected; code that imports or catches ``ListOrTuppleError`` specifically must be updated to catch ``TypeError``
  (`#807 <https://github.com/aiidalab/aiidalab-widgets-base/pull/807>`__).
* ``ProcessFollowerWidget.on_completed()`` now raises a ``RuntimeError`` (instead of referencing a nonexistent ``CantRegisterCallbackError`` class) when called after process-following has already started
  (`#780 <https://github.com/aiidalab/aiidalab-widgets-base/pull/780>`__).
