"""Reusable widgets for AiiDAlab applications."""

from aiida.manage import get_profile

_WARNING_TEMPLATE = """
<div style="background-color: #f7f7f7; border: 2px solid #e0e0e0; padding: 20px; border-radius: 5px;">
    <p style="font-size: 16px; font-weight: bold; color: #ff5733;">Warning:</p>
    <p style="font-size: 14px;">The default profile '<span style="font-style: italic;">{profile}</span>' was loaded automatically. This behavior will be removed in the <span style="font-style: italic;">{version}</span>. Please load the profile manually before loading modules from aiidalab-widgets-base by adding the following code at the beginning cell of the notebook:</p>
    <pre style="background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc; font-family: 'Courier New', monospace;">
from aiida import load_profile
load_profile();</pre>
</div>
"""


# We only detect profile and throw a warning if it is on the notebook
# It is not necessary to do this in the unit tests
def is_running_in_jupyter():
    try:
        from IPython import get_ipython

        if get_ipython() is not None:
            return True
        else:
            return False
    except NameError:
        return False


# load the default profile if no profile is loaded, and raise a deprecation warning
# this is a temporary solution to avoid breaking existing notebooks
# this will be removed in the next major release
if is_running_in_jupyter() and get_profile() is None:
    # if no profile is loaded, load the default profile and raise a deprecation warning
    from aiida import load_profile
    from IPython.display import HTML, display

    load_profile()

    profile = get_profile()
    assert profile is not None, "Failed to load the default profile"

    # raise a deprecation warning
    warning = HTML(_WARNING_TEMPLATE.format(profile=profile.name, version="v3.0.0"))
    display(warning)

from .computational_resources import (
    ComputationalResourcesWidget,
    ComputerDropdownWidget,
)
from .databases import CodQueryWidget, OptimadeQueryWidget
from .elns import ElnConfigureWidget, ElnExportWidget, ElnImportWidget
from .export import ExportButtonWidget
from .nodes import NodesTreeWidget, OpenAiidaNodeInAppWidget
from .process import (
    ProcessCallStackWidget,
    ProcessFollowerWidget,
    ProcessInputsWidget,
    ProcessListWidget,
    ProcessMonitor,
    ProcessNodesTreeWidget,
    ProcessOutputsWidget,
    ProcessReportWidget,
    ProgressBarWidget,
    RunningCalcJobOutputWidget,
    SubmitButtonWidget,
)
from .structures import (
    BasicCellEditor,
    BasicStructureEditor,
    SmilesWidget,
    StructureBrowserWidget,
    StructureExamplesWidget,
    StructureManagerWidget,
    StructureUploadWidget,
)
from .viewers import AiidaNodeViewWidget, register_viewer_widget, viewer
from .wizard import WizardAppWidget, WizardAppWidgetStep

__all__ = [
    "AiidaNodeViewWidget",
    "BasicStructureEditor",
    "BasicCellEditor",
    "CodeDatabaseWidget",
    "CodeDropdown",
    "CodQueryWidget",
    "ComputerDatabaseWidget",
    "ComputationalResourcesWidget",
    "ComputerDropdownWidget",
    "ElnConfigureWidget",
    "ElnExportWidget",
    "ElnImportWidget",
    "ExportButtonWidget",
    "MultiStructureUploadWidget",
    "NodesTreeWidget",
    "OpenAiidaNodeInAppWidget",
    "OptimadeQueryWidget",
    "ProcessCallStackWidget",
    "ProcessFollowerWidget",
    "ProcessInputsWidget",
    "ProcessListWidget",
    "ProcessMonitor",
    "ProcessNodesTreeWidget",
    "ProcessOutputsWidget",
    "ProcessReportWidget",
    "ProgressBarWidget",
    "RunningCalcJobOutputWidget",
    "SmilesWidget",
    "StructureBrowserWidget",
    "StructureExamplesWidget",
    "StructureManagerWidget",
    "StructureUploadWidget",
    "SubmitButtonWidget",
    "WizardAppWidget",
    "WizardAppWidgetStep",
    "register_viewer_widget",
    "viewer",
]

__version__ = "2.3.0a0"
