**********************
CDXML structure import
**********************

:class:`CdxmlUploadWidget` converts ChemDraw CDXML sketches into planar
:class:`ase.Atoms` structures. Molecular sketches receive implicit
hydrogens from their explicit bond orders. Square-bracketed repeat units are
converted to one-dimensional periodic structures.

When a CDXML document contains several chemical fragments, the widget displays
a structure selector. Each fragment is associated one-to-one with a nearby
caption, using the local drawing bond length to reject unrelated distant text.
Fragments without a nearby caption are identified as ``Structure 1``,
``Structure 2``, and so on.

.. code-block:: python

   from aiidalab_widgets_base import CdxmlUploadWidget

   cdxml_importer = CdxmlUploadWidget(title="CDXML")
   display(cdxml_importer)

The optional **Clean up 2D carbon geometry** control rescales arbitrary drawing
units from explicit C-C bonds and regularizes the carbon network globally.
The operation preserves the explicit topology and planar embedding, keeps C-C
distances between 1.35 and 1.60 Angstrom, and does not force fused rings to
become independent regular polygons.
