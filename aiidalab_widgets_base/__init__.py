"""Reusable widgets for AiiDAlab applications."""
from aiida import load_profile

load_profile()

from .computational_resources import (
    CodeDropdown,
    ComputationalResourcesWidget,
    ComputerDropdown,
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
    "CodeDropdown",
    "CodQueryWidget",
    "ComputationalResourcesWidget",
    "ComputerDropdown",
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
    "SshComputerSetup",
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

__version__ = "1.2.0"
