"""Some utility functions used acrross the repository."""
from functools import wraps

import more_itertools as mit
import numpy as np
from ase.io import read


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
            raise AttributeError(f"'{obj}' object has no attirubte '{key}'")


def get_ase_from_file(fname, format=None):  # pylint: disable=redefined-builtin
    """Get ASE structure object."""
    if format == "cif":
        traj = read(fname, format=format, index=":", store_tags=True)
    else:
        traj = read(fname, format=format, index=":")
    if not traj:
        print(f"Could not read any information from the file {fname}")
        return False
    if len(traj) > 1:
        print(
            "Warning: Uploaded file {} contained more than one structure. Selecting the first one.".format(
                fname
            )
        )
    return traj[0]


def find_ranges(iterable):
    """Yield range of consecutive numbers."""
    for group in mit.consecutive_groups(iterable):
        group = list(group)
        if len(group) == 1:
            yield group[0]
        else:
            yield group[0], group[-1]


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
        return list(), False
    for rng in ranges:
        try:
            start, end = rng.split("..")
            singles += [i + shift for i in range(int(start), int(end) + 1)]
        except ValueError:
            return list(), False
    return singles, True


def yield_for_change(widget, attribute):
    """Pause a generator to wait for a widget change event.

    Taken from: https://ipywidgets.readthedocs.io/en/7.6.5/examples/Widget%20Asynchronous.html#Generator-approach

    This is a decorator for a generator function which pauses the generator on yield
    until the given widget attribute changes. The new value of the attribute is
    sent to the generator and is the value of the yield.
    """

    def f(iterator):
        @wraps(iterator)
        def inner():
            i = iterator()

            def next_i(change):
                try:
                    i.send(change.new)
                except StopIteration:
                    widget.unobserve(next_i, attribute)

            widget.observe(next_i, attribute)
            # start the generator
            next(i)

        return inner

    return f


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
