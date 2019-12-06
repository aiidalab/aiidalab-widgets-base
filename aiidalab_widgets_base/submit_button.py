"""Submit button to run an AiiDA process."""
from __future__ import print_function
from __future__ import absolute_import

import ipywidgets as ipw
from IPython.display import clear_output
from aiida.engine import submit


class SubmitButtonWidget(ipw.VBox):
    """Submit button class that creates submit button jupyter widget."""

    def __init__(self, process, widgets_values):
        """ Submit Button
        :process: work chain to run
        :param_funtion: the function that generates input parameters dictionary
        """
        self.process = None
        self._process_class = process
        self.widgets_values = widgets_values
        self.btn_submit = ipw.Button(description="Submit", disabled=False)
        self.btn_submit.on_click(self.on_btn_submit_press)
        self.submit_out = ipw.Output()
        children = [
            self.btn_submit,
            self.submit_out,
        ]
        super(SubmitButtonWidget, self).__init__(children=children)
        ### ---------------------------------------------------------
    def on_click(self, function):
        self.btn_submit.on_click(function)

    def on_btn_submit_press(self, _):
        """When submit button is pressed."""
        with self.submit_out:
            clear_output()
            self.btn_submit.disabled = True
            input_dict = self.widgets_values()
            self.process = submit(self._process_class, **input_dict)
            print("Submitted process ", self.process)
            print("")
            return
