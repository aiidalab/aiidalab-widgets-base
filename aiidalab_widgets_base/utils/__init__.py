"""Some utility functions used acrross the repository."""

import itertools
import operator
import threading
from enum import Enum
from typing import Any

import ase
import ase.io
import ipywidgets as ipw
import numpy as np
import traitlets as tl
from aiida.plugins import DataFactory

CifData = DataFactory("core.cif")  # pylint: disable=invalid-name
StructureData = DataFactory("core.structure")  # pylint: disable=invalid-name
TrajectoryData = DataFactory("core.array.trajectory")  # pylint: disable=invalid-name


def valid_arguments(arguments, valid_args):
    """Check whether provided arguments are valid."""
    result = {}
    for key, value in arguments.items():
        if key in valid_args:
            if isinstance(value, (tuple, list)):
                result[key] = "\n".join(value)
            else:
                result[key] = value
    return result


def predefine_settings(obj, **kwargs):
    """Specify some pre-defined settings."""
    for key, value in kwargs.items():
        if hasattr(obj, key):
            setattr(obj, key, value)
        else:
            raise AttributeError(f"{obj!r} object has no attribute {key!r}")


def get_ase_from_file(fname, file_format=None):  # pylint: disable=redefined-builtin
    """Get ASE structure object."""
    # store_tags parameter is useful for CIF files
    # https://wiki.fysik.dtu.dk/ase/ase/io/formatoptions.html#cif
    if file_format == "cif":
        traj = ase.io.read(fname, format=file_format, index=":", store_tags=True)
    else:
        traj = ase.io.read(fname, format=file_format, index=":")
    if not traj:
        raise ValueError(f"Could not read any information from the file {fname}")
    return traj


def find_ranges(iterable):
    """Yield range of consecutive numbers."""
    for grp in _consecutive_groups(iterable):
        group = list(grp)
        if len(group) == 1:
            yield group[0]
        else:
            yield group[0], group[-1]


def _consecutive_groups(iterable, ordering=lambda x: x):
    """Yield groups of consecutive items using :func:`itertools.groupby`.
    The *ordering* function determines whether two items are adjacent by
    returning their position.

    This is a vendored version of more_itertools.consecutive_groups
    https://more-itertools.readthedocs.io/en/v10.3.0/_modules/more_itertools/more.html#consecutive_groups
    Distributed under MIT license: https://more-itertools.readthedocs.io/en/v10.3.0/license.html
    Thank you Bo Bayles for the original implementation. <3
    """
    for _, g in itertools.groupby(
        enumerate(iterable), key=lambda x: x[0] - ordering(x[1])
    ):
        yield map(operator.itemgetter(1), g)


def list_to_string_range(lst, shift=1):
    """Converts a list like [0, 2, 3, 4] into a string like '1 3..5'.

    Shift used when e.g. for a user interface numbering starts from 1 not from 0"""
    return " ".join(
        [
            f"{t[0] + shift}..{t[1] + shift}"
            if isinstance(t, tuple)
            else str(t + shift)
            for t in find_ranges(sorted(lst))
        ]
    )


def string_range_to_list(strng, shift=-1):
    """Converts a string like '1 3..5' into a list like [0, 2, 3, 4].

    Shift used when e.g. for a user interface numbering starts from 1 not from 0"""
    singles = [int(s) + shift for s in strng.split() if s.isdigit()]
    ranges = [r for r in strng.split() if ".." in r]
    if len(singles) + len(ranges) != len(strng.split()):
        return [], False
    for rng in ranges:
        try:
            start, end = rng.split("..")
            singles += [i + shift for i in range(int(start), int(end) + 1)]
        except ValueError:
            return [], False
    return singles, True


def get_formula(data_node):
    """A wrapper for getting a molecular formula out of the AiiDA Data node"""
    if isinstance(data_node, TrajectoryData):
        # TrajectoryData can only hold structures with the same chemical formula,
        # so this approach is sound.
        stepid = data_node.get_stepids()[0]
        return data_node.get_step_structure(stepid).get_formula()
    elif isinstance(data_node, StructureData):
        return data_node.get_formula()
    elif isinstance(data_node, CifData):
        return data_node.get_ase().get_chemical_formula()
    else:
        raise TypeError(f"Cannot get formula from node {type(data_node)}")


class PinholeCamera:
    def __init__(self, matrix):
        self.matrix = np.reshape(matrix, (4, 4)).transpose()

    def screen_to_vector(self, move_vector):
        """Converts vector from the screen coordinates to the normalized vector in 3D."""
        move_vector[0] = -move_vector[0]  # the x axis seem to be reverted in nglview.
        res = np.append(np.array(move_vector), [0])
        res = self.inverse_matrix.dot(res)
        res /= np.linalg.norm(res)
        return res[0:3]

    @property
    def inverse_matrix(self):
        return np.linalg.inv(self.matrix)


class _StatusWidgetMixin(tl.HasTraits):
    """Show temporary messages for example for status updates.
    This is a mixin class that is meant to be part of an inheritance
    tree of an actual widget with a 'value' traitlet that is used
    to convey a status message. See the non-private classes below
    for examples.
    """

    message = tl.Unicode(default_value="", allow_none=True)
    new_line = "\n"

    def __init__(self, clear_after=3, *args, **kwargs):
        self._clear_timer = None
        self._clear_after = clear_after
        self._message_stack = []
        super().__init__(*args, **kwargs)

    def _clear_value(self):
        """Set widget .value to be an empty string."""
        if self._message_stack:
            self._message_stack.pop(0)
            self.value = self.new_line.join(self._message_stack)
        else:
            self.value = ""

    def show_temporary_message(self, value, clear_after=None):
        """Show a temporary message and clear it after the given interval."""
        clear_after = clear_after or self._clear_after
        if value:
            self._message_stack.append(value)
            self.value = self.new_line.join(self._message_stack)

            # Start new timer that will clear the value after the specified interval.
            self._clear_timer = threading.Timer(self._clear_after, self._clear_value)
            self._clear_timer.start()
            self.message = None


class StatusHTML(_StatusWidgetMixin, ipw.HTML):
    """Show temporary HTML messages for example for status updates."""

    new_line = "<br>"

    # This method should be part of _StatusWidgetMixin, but that does not work
    # for an unknown reason.
    @tl.observe("message")
    def _observe_message(self, change):
        self.show_temporary_message(change["new"])


# Define the message levels as Enum
class MessageLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "danger"
    SUCCESS = "success"


def wrap_message(message, level=MessageLevel.INFO):
    """Wrap message into HTML code with the given level."""
    # mapping level to fa icon
    # https://fontawesome.com/v4.7.0/icons/
    mapping = {
        MessageLevel.INFO: "info-circle",
        MessageLevel.WARNING: "exclamation-triangle",
        MessageLevel.ERROR: "exclamation-circle",
        MessageLevel.SUCCESS: "check-circle",
    }

    # The message is wrapped into a div with the class "alert" and the icon of the given level
    return f"""
        <div class="alert alert-{level.value}" role="alert" style="margin-bottom: 0px; padding: 6px 12px;">
            <i class="fa fa-{mapping[level]}"></i>{message}
        </div>
    """


def ase2spglib(ase_structure: ase.Atoms) -> tuple[Any, Any, Any]:
    """
    Convert ase Atoms instance to spglib cell in the format defined at
    https://spglib.github.io/spglib/python-spglib.html#crystal-structure-cell
    """
    lattice = ase_structure.get_cell()
    positions = ase_structure.get_scaled_positions()
    numbers = ase_structure.get_atomic_numbers()

    return (lattice, positions, numbers)
