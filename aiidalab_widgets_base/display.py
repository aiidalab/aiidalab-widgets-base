from __future__ import print_function

import importlib
from IPython.display import display

RECOGNIZED_AIIDA_DATA_VISUALIZERS = {
    'data.parameter.ParameterData.' : 'ParameterDataVisualizer',
    'data.structure.StructureData.' : 'StructureDataVisualizer',
    'data.cif.CifData.'             : 'StructureDataVisualizer',
    'data.folder.FolderData.'       : 'FolderDataVisualizer',
    'data.array.bands.BandsData.'   : 'BandsDataVisualizer',
}

def aiidalab_display(obj, downloadable=True):
    """Function that is able to display properly differnt AiiDA data types"""
    from aiidalab_widgets_base import aiida_visualizers
    if hasattr(obj, 'type') and obj.type in RECOGNIZED_AIIDA_DATA_VISUALIZERS:
        aiidavis_type = RECOGNIZED_AIIDA_DATA_VISUALIZERS[obj.type]
        imported = getattr(aiida_visualizers, aiidavis_type)
        display(imported(obj, downloadable=downloadable))
    else:
        display(obj)