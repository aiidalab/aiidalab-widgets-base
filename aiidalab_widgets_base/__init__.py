"""Reusable widgets for AiiDAlab applications."""
from aiida import load_profile

load_profile()

from .codes import AiiDACodeSetup, CodeDropdown
from .computational_resources import (
    ComputationalResourcesWidget,
    ComputerDropdownWidget,
)
from .computers import AiidaComputerSetup, ComputerDropdown, SshComputerSetup
from .databases import (
    CodeDatabaseWidget,
    CodQueryWidget,
    ComputerDatabaseWidget,
    OptimadeQueryWidget,
)
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
    "AiiDACodeSetup",
    "AiidaComputerSetup",
    "AiidaNodeViewWidget",
    "BasicStructureEditor",
    "CodeDatabaseWidget",
    "CodeDropdown",
    "CodQueryWidget",
    "ComputerDatabaseWidget",
    "ComputationalResourcesWidget",
    "ComputerDropdown",
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

__version__ = "1.3.1"
