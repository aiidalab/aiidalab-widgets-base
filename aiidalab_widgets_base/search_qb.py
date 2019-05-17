from __future__ import absolute_import
from aiida.orm.querybuilder import QueryBuilder
from aiida.orm import StructureData


def formula_in_qb(formula):
    # search for existing structures
    qb = QueryBuilder()
    qb.append(StructureData, filters={'extras.formula': formula})
    return [[n[0].get_ase(), n[0].pk] for n in qb.iterall()]
