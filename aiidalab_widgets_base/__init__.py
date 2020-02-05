"""Reusable widgets for AiiDA lab applications."""
# pylint: disable=unused-import
from aiida import load_profile
load_profile()

from .codes import CodeDropdown, AiiDACodeSetup, valid_aiidacode_args  # noqa
from .computers import SshComputerSetup, valid_sshcomputer_args  # noqa
from .computers import AiidaComputerSetup, valid_aiidacomputer_args  # noqa
from .computers import ComputerDropdown  # noqa
from .databases import CodQueryWidget  # noqa
#from .editors import editor  # noqa
from .export import ExportButtonWidget  # noqa
from .process import ProcessFollowerWidget, ProgressBarWidget, RunningCalcJobOutputWidget, SubmitButtonWidget  # noqa
from .structures import StructureManagerWidget  # noqa
from .structures import StructureBrowserWidget, StructureExamplesWidget, StructureUploadWidget, SmilesWidget  # noqa
from .structures_multi import MultiStructureUploadWidget  # noqa
from .viewers import viewer  # noqa

__version__ = "1.0.0a8"
