"""Reusable widgets for AiiDAlab applications."""
from aiida import load_profile

load_profile()

from .codes import CodeDropdown, AiiDACodeSetup
from .computers import SshComputerSetup
from .computers import AiidaComputerSetup
from .computers import ComputerDropdown
from .databases import (
    CodQueryWidget,
    CodeDatabaseWidget,
    ComputerDatabaseWidget,
    OptimadeQueryWidget,
)
from .export import ExportButtonWidget
from .nodes import NodesTreeWidget
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
from .structures import StructureManagerWidget
from .structures import (
    StructureBrowserWidget,
    StructureExamplesWidget,
    StructureUploadWidget,
    SmilesWidget,
)
from .structures import BasicStructureEditor
from .viewers import viewer
from .viewers import register_viewer_widget

from .wizard import WizardAppWidget
from .wizard import WizardAppWidgetStep


__all__ = [
    "AiiDACodeSetup",
    "AiidaComputerSetup",
    "BasicStructureEditor",
    "CodQueryWidget",
    "CodeDatabaseWidget",
    "CodeDropdown",
    "ComputerDatabaseWidget",
    "ComputerDropdown",
    "ExportButtonWidget",
    "MultiStructureUploadWidget",
    "NodesTreeWidget",
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

__version__ = "1.0.0b18"
