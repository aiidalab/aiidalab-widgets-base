"""Some utility functions used acrross the repository."""


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
