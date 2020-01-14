"""Some utility functions used acrross the repository."""

from __future__ import absolute_import
from __future__ import print_function
from functools import wraps


def valid_arguments(arguments, valid_args):
    """Check whether provided arguments are valid."""
    result = {}
    for key, value in arguments.items():
        if key in valid_args:
            if isinstance(value, (tuple, list)):
                result[key] = '\n'.join(value)
            else:
                result[key] = value
    return result


def predefine_settings(obj, **kwargs):
    """Specify some pre-defined settings."""
    for key, value in kwargs.items():
        if hasattr(obj, key):
            setattr(obj, key, value)
        else:
            raise AttributeError("'{}' object has no attirubte '{}'".format(obj, key))


def get_ase_from_file(fname):
    """Get ASE structure object."""
    from ase.io import read
    try:
        traj = read(fname, index=":")
    except Exception as exc:  # pylint: disable=broad-except
        if exc.args:
            print((' '.join([str(c) for c in exc.args])))
        else:
            print("Unknown error")
        return False
    if not traj:
        print(("Could not read any information from the file {}".format(fname)))
        return False
    if len(traj) > 1:
        print(("Warning: Uploaded file {} contained more than one structure. I take the first one.".format(fname)))
    return traj[0]


def requires_open_babel(wrapped):
    """Decorator for functions that require the OpenBabel library.

    Check for OpenBabel and raise ImportError with informative error message
    in case that the library is not available.
    """

    @wraps(wrapped)
    def inner(*args, **kwargs):
        try:
            import openbabel  # pylint: disable=unused-import
        except ImportError:
            raise ImportError("The '{}' function requires the OpenBabel library, "
                              "but the library was not found.".format(wrapped))
        else:
            return wrapped(*args, **kwargs)

    return inner
