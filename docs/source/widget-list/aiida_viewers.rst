.. _widget-list:aiida_viewers:

*************
AiiDA Viewers
*************

This module contains the viewers, which are used to visualize AiiDA objects.

**How to visualize an AiiDA object**
.. _widget-list:aiida_viewers:how-to-visualize-an-aiida-object:

The simples way is to import the :py:meth:`~aiidalab_widgets_base.viewer` function and call it with the object:

.. code-block:: python

    from aiida import orm
    from aiidalab_widgets_base import viewer

    p = Dict(dict={
        'parameter 1' : 'some string',
        'parameter 2' : 2,
        'parameter 3' : 3.0,
        'parameter 4' : [1, 2, 3],
    })
    vwr = viewer(p.store(), downloadable=True)
    display(vwr)
