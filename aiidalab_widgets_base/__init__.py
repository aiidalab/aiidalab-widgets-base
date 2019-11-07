"""Reusable widgets for AiiDA lab applications."""
# pylint: disable=unused-import
from __future__ import absolute_import
from aiida import load_profile
load_profile()

from .codes import CodeDropdown, AiiDACodeSetup, valid_aiidacode_args  # noqa
from .computers import SshComputerSetup, valid_sshcomputer_args  # noqa
from .computers import AiidaComputerSetup, valid_aiidacomputer_args  # noqa
from .databases import CodQueryWidget  # noqa
from .display import aiidalab_display  # noqa
from .export import ExportButton  # noqa
from .metadata import MetadataWidget  # noqa
from .process import ProgressBar, RunningCalcJobOutput  # noqa
from .structures import StructureUploadWidget  # noqa
from .structure_browser import StructureBrowserWidget  # noqa
from .structures_multi import MultiStructureUploadWidget  # noqa
from .submit_button import SubmitButtonWidget  # noqa
__version__ = "1.0.0a7"
