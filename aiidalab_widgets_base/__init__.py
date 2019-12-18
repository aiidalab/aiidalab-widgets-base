"""Reusable widgets for AiiDA lab applications."""
# pylint: disable=unused-import
from __future__ import absolute_import
from aiida import load_profile
load_profile()

from .aiida_viewers import viewer  # noqa
from .codes import CodeDropdown, AiiDACodeSetup, valid_aiidacode_args  # noqa
from .computers import SshComputerSetup, valid_sshcomputer_args  # noqa
from .computers import AiidaComputerSetup, valid_aiidacomputer_args  # noqa
from .computers import ComputerDropdown  # noqa
from .databases import CodQueryWidget  # noqa
from .export import ExportButtonWidget  # noqa
from .metadata import MetadataWidget  # noqa
from .process import ProcessFollowerWidget, ProgressBarWidget, RunningCalcJobOutputWidget  # noqa
from .structures import StructureUploadWidget, StructureBrowserWidget, SmilesWidget  # noqa
from .structures_multi import MultiStructureUploadWidget  # noqa
from .submit_button import SubmitButtonWidget  # noqa
__version__ = "1.0.0a7"
