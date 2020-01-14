"""Some utility functions used acrross the repository."""

import ipywidgets as ipw


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
        print(("Warning: Uploaded file {} contained more than one structure. Selecting the first one.".format(fname)))
    return traj[0]


def find_ranges(iterable):
    """Yield range of consecutive numbers."""
    import more_itertools as mit
    for group in mit.consecutive_groups(iterable):
        group = list(group)
        if len(group) == 1:
            yield group[0]
        else:
            yield group[0], group[-1]


def string_range_to_set(strng):
    """Convert string like '1 3..5' into the set like {1, 3, 4, 5}."""
    singles = [int(s) for s in strng.split() if s.isdigit()]
    ranges = [r for r in strng.split() if '..' in r]
    if len(singles) + len(ranges) != len(strng.split()):
        return set(), False
    for rng in ranges:
        try:
            start, end = rng.split('..')
            singles += [i for i in range(int(start), int(end) + 1)]
        except ValueError:
            return set(), False
    return set(singles), True


class CopyToClipboardButton(ipw.Button):
    """Button to copy text to clipboard."""

    def __init__(self, text_provider_function=None, **kwargs):
        self.text_provider_function = text_provider_function
        super().__init__(**kwargs)
        super().on_click(self.copy_to_clipboard)

    def copy_to_clipboard(self, change=None):  # pylint:disable=unused-argument
        """Copy text to clipboard."""
        from IPython.display import Javascript, display

        javas = Javascript("""
           function copyStringToClipboard (str) {{
               // Create new element
               var el = document.createElement('textarea');
               // Set value (string to be copied)
               el.value = str;
               // Set non-editable to avoid focus and move outside of view
               el.setAttribute('readonly', '');
               el.style = {{position: 'absolute', left: '-9999px'}};
               document.body.appendChild(el);
               // Select text inside element
               el.select();
               // Copy text to clipboard
               document.execCommand('copy');
               // Remove temporary element
               document.body.removeChild(el);
            }}
            copyStringToClipboard("{selection}");
       """.format(selection=self.text_to_copy))  # for the moment works for Chrome, but doesn't work for Firefox
        display(javas)

    @property
    def text_to_copy(self):
        if not self.text_provider_function:
            raise ValueError("Text provider function is not registered.")
        return self.text_provider_function()
