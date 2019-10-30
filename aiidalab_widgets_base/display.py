"""This module contains the AiiDA lab display function capble of recognizing the object type and
   displaying it properly."""
from __future__ import print_function

from __future__ import absolute_import
from IPython.display import display

AIIDA_VISUALIZER_MAPPING = {
    'data.dict.Dict.': 'DictVisualizer',
    'data.structure.StructureData.': 'StructureDataVisualizer',
    'data.cif.CifData.': 'StructureDataVisualizer',
    'data.folder.FolderData.': 'FolderDataVisualizer',
    'data.array.bands.BandsData.': 'BandsDataVisualizer',
}


def aiidalab_display(obj, downloadable=True, **kwargs):
    """Display AiiDA data types in Jupyter notebooks.

    :param downloadable: If True, add link/button to download content of displayed AiiDA object.

    Defers to IPython.display.display for any objects it does not recognize.
    """
    from aiidalab_widgets_base import aiida_visualizers
    try:
        visualizer = getattr(aiida_visualizers, AIIDA_VISUALIZER_MAPPING[obj.node_type])
        display(visualizer(obj, downloadable=downloadable), **kwargs)
    except KeyError:
        display(obj, **kwargs)
