"""Some useful classes used acrross the repository."""

import ipywidgets as ipw
from traitlets import Unicode


class CopyToClipboardButton(ipw.Button):
    """Button to copy text to clipboard."""

    value = Unicode(allow_none=True)  # Traitlet that contains a string to copy.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
       """.format(selection=self.value))  # For the moment works for Chrome, but doesn't work for Firefox.
        if self.value:  # If no value provided - do nothing.
            display(javas)
