"""Useful functions that provide access to some data."""

import ipywidgets as ipw
import numpy as np
from ase import Atom, Atoms

# The first atom is anchoring, so the new bond will be connecting it
# The direction of the new bond is (-1, -1, -1).
FUNCTIONAL_GROUPS = {
    "Select functional group": 0,
    "Methyl -CH3": [
        ("C", 0, 0, 0),
        ("H", 0.23962342, -0.47699124, 0.78585262),
        ("H", 0.78584986, 0.23962732, -0.47698795),
        ("H", -0.47699412, 0.78585121, 0.23962671),
    ],
    "Methylene =CH2": [
        ("C", 0, 0, 0),
        ("H", -0.39755349, 0.59174911, 0.62728004),
        ("H", 0.94520686, -0.04409933, -0.07963039),
    ],
    "Hydroxy -OH": [("O", 0, 0, 0), ("H", 0.87535922, -0.3881659, 0.06790889)],
    "Amine -NH2": [
        ("N", 0, 0, 0),
        ("H", 0.7250916, -0.56270993, 0.42151063),
        ("H", -0.56261958, 0.4215284, 0.72515241),
    ],
}


class FunctionalGroupSelectorWidget(ipw.Dropdown):
    """Class to select functional groups that are returned as `Atoms` object"""

    def __init__(self, value=0, description="Select functional group", **kwargs):
        self.style = {"description_width": "initial"}
        self.layout = {"width": "initial"}
        super().__init__(
            value=value,
            description=description,
            options=tuple((key, value) for key, value in FUNCTIONAL_GROUPS.items()),
            **kwargs,
        )

    def rotate(self, align_to=(0, 0, 1), remove_anchor=False):
        """Rotate group in such a way that vector which was (-1,-1,-1)
        is alligned with align_to."""

        vect = np.array(align_to)
        norm = np.linalg.norm(vect)

        if self.value == 0:
            return None

        mol = Atoms()
        for atm in self.value:
            mol.append(Atom(atm[0], atm[1:]))

        # Bad cases.
        if norm == 0.0:
            vect = np.array((1, 1, 1)) / np.sqrt(3)
        else:
            vect = vect / norm

        mol.rotate((1, 1, 1), vect)

        if remove_anchor:
            del mol[0]

        return mol

    @property
    def anchoring_atom(self):
        """Return anchoring atom chemical symbol."""
        if self.value == 0:
            return None
        return self.value[0][0]


# LigandSelectorWidget is deprecated
LigandSelectorWidget = FunctionalGroupSelectorWidget
