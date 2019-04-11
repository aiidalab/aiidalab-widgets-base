# pylint: disable=unused-import
from aiida import load_dbenv, is_dbenv_loaded
from aiida.backends import settings
if not is_dbenv_loaded():
    load_dbenv(profile=settings.AIIDADB_PROFILE)

from .structures import StructureUploadWidget  # noqa
from .structures_multi import MultiStructureUploadWidget  # noqa
from .codes import CodeDropdown, AiiDACodeSetup, extract_aiidacodesetup_arguments # noqa
from .computers import SshComputerSetup, extract_sshcomputersetup_arguments # noqa
from .computers import AiidaComputerSetup, extract_aiidacomputer_arguments # noqa

__version__ = "0.2.0a1"
