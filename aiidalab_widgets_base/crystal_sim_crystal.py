import itertools
import numpy as np
import spglib

from ase.spacegroup import crystal
from ase.data import atomic_numbers, atomic_names
from ase.spacegroup import Spacegroup
from numpy.linalg import norm


def ase_to_spgcell(ase_atoms):
    return (ase_atoms.get_cell(),
            ase_atoms.get_scaled_positions(),
            ase_atoms.get_atomic_numbers())
def check_crystal_equivalence(crystal_a, crystal_b):
    """Function that identifies whether two crystals are equivalent"""

    # getting symmetry datasets for both crystals
    cryst_a = spglib.get_symmetry_dataset(ase_to_spgcell(crystal_a), symprec=1e-5, angle_tolerance=-1.0, hall_number=0)
    cryst_b = spglib.get_symmetry_dataset(ase_to_spgcell(crystal_b), symprec=1e-5, angle_tolerance=-1.0, hall_number=0)

    samecell = np.allclose(cryst_a['std_lattice'], cryst_b['std_lattice'], atol=1e-5)
    samenatoms = len(cryst_a['std_positions']) == len(cryst_b['std_positions'])
    samespg = cryst_a['number'] == cryst_b['number']
    
    def test_rotations_translations(cryst_a, cryst_b, repeat):
        cell = cryst_a['std_lattice']
        pristine = crystal('Mg', [(0, 0., 0.)], 
                           spacegroup=int(cryst_a['number']),
                           cellpar=[cell[0]/repeat[0], cell[1]/repeat[1], cell[2]/repeat[2]]).repeat(repeat)

        sym_set_p = spglib.get_symmetry_dataset(ase_to_spgcell(pristine), symprec=1e-5,
                                               angle_tolerance=-1.0, hall_number=0)

        for _,trans in enumerate(zip(sym_set_p['rotations'], sym_set_p['translations'])):
            pnew=(np.matmul(trans[0],cryst_a['std_positions'].T).T + trans[1]) % 1.0
            fulln = np.concatenate([cryst_a['std_types'][:, None], pnew], axis=1)
            fullb = np.concatenate([cryst_b['std_types'][:, None], cryst_b['std_positions']], axis=1)
            sorted_n = np.array(sorted([ list(row) for row in list(fulln) ]))
            sorted_b = np.array(sorted([ list(row) for row in list(fullb) ]))
            if np.allclose(sorted_n, sorted_b, atol=1e-5):
                return True
        return False

    if samecell and samenatoms and samespg:
        cell = cryst_a['std_lattice']
        # we assume there are no crystals with a lattice parameter smaller than 2 A
        rng1 = range(1, int(norm(cell[0])/2.))
        rng2 = range(1, int(norm(cell[1])/2.))
        rng3 = range(1, int(norm(cell[2])/2.))

        for repeat in itertools.product(rng1, rng2, rng3):
            if test_rotations_translations(cryst_a, cryst_b, repeat):
                return True

    return False
