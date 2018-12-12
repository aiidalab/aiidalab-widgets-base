from __future__ import print_function
from collections import OrderedDict
from IPython.display import display, clear_output, HTML

from aiida import load_dbenv, is_dbenv_loaded
from aiida.backends import settings
if not is_dbenv_loaded():
    load_dbenv(profile=settings.AIIDADB_PROFILE)

from aiida.orm.querybuilder import QueryBuilder
from aiida.orm.data.structure import StructureData
from aiida.orm.calculation import Calculation

def formula_in_qb(formula):
    # search for existing structures
    qb = QueryBuilder()
    qb.append(StructureData, filters={'extras.formula':formula})
    return [[n[0].get_ase(),n[0].pk] for n in qb.iterall()]
