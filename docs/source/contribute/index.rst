************
Contributing
************

Contributions to the AiiDAlab widgets are highly welcome and can take different forms:

* Contribute a widget you created that would be of general interest to AiiDAlab users.
* `Report bugs <https://github.com/aiidalab/aiidalab-widgets-base/issues>`_.
* `Feature requests <https://github.com/aiidalab/aiidalab-widgets-base/issues>`_.
* Help us improve the documentation of widgets.

**************
Widget styling
**************

Though ``ipywidgets`` does provide some basic styling options via the ``layout`` and ``style`` attributes, it is often not enough to create a visually appealing widget.
As such, we recommend the use of `CSS <https://www.w3schools.com/css/>`_ stylesheets to style your widgets.
These may be packaged under ``aiidalab_widgets_base/static/styles``, which are automatically loaded on import via the ``load_css`` utility.

A ``global.css`` stylesheet is made available for global html-tag styling and ``ipywidgets`` or ``Jupyter`` style overrides.
For more specific widgets and components, please add a dedicated stylesheet.
Note that all stylesheets in the ``styles`` directory will be loaded on import.

We recommend using classes to avoid style leaking outside of the target widget.
We also advise causion when using the `!important <https://www.w3schools.com/css/css_important.asp>`_ flag on CSS properties, as it may interfere with other stylesheets.

If you are unsure about the styling of your widget, feel free to ask for help on the `AiiDAlab Discourse channel <https://aiida.discourse.group/tag/aiidalab>`_.
