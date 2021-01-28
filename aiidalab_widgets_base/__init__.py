"""Reusable widgets for AiiDAlab applications."""
# pylint: disable=unused-import,wrong-import-position
from aiida import load_profile
load_profile()

from .codes import CodeDropdown, AiiDACodeSetup
from .computers import SshComputerSetup
from .computers import AiidaComputerSetup
from .computers import ComputerDropdown
from .databases import CodQueryWidget, CodeDatabaseWidget, ComputerDatabaseWidget, OptimadeQueryWidget
from .export import ExportButtonWidget
from .process import ProgressBarWidget, ProcessFollowerWidget, ProcessInputsWidget, ProcessOutputsWidget
from .process import ProcessCallStackWidget, RunningCalcJobOutputWidget, SubmitButtonWidget, ProcessReportWidget
from .process import ProcessListWidget
from .structures import StructureManagerWidget
from .structures import StructureBrowserWidget, StructureExamplesWidget, StructureUploadWidget, SmilesWidget
from .structures import BasicStructureEditor
from .structures_multi import MultiStructureUploadWidget
from .viewers import viewer

__version__ = "1.0.0b15"
