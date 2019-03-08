from __future__ import print_function
from __future__ import absolute_import

import ipywidgets as ipw
from traitlets import observe, Dict


class SubmitWorkChainWidget(ipw.VBox):
    inputs = Dict()

    def __init__(self,
                 workchain,
                 inputs=None,
                 text="Submit",
                 validate_fn=None,
                 **kwargs):
        """ Submit a workchain.

        Usage example::

              # submit button greyed out (no inputs provided)
              sm = SubmitWorkChainWidget(workchain=MyWorkChain)
              display(sm)

              # ... setting up the inputs

              # providing inputs triggers validation (if specified)
              # and enables submit button 
              sm.inputs = my_inputs 

        :param workchain: AiiDA WorkChain class to be submitted
        :type workchain: class

        :param inputs: Dictionary of workchain inputs. This can be provided at a later stage.
            Keys must match the input spec of the workchain.
        :type inputs: dict

        :param validate_fn: Function to validate input parameters.
            By default, no validation is performed.
        :type validate_fn: function

        :param text: Text to display on the submit button
        :type text: str

        """
        self._workchain = workchain
        if self.inputs:
            self.inputs = inputs
        self._validate_fn = validate_fn
        self.btn_submit = ipw.Button(description=text, disabled=True)

        children = [self.btn_submit]

        super(SubmitWorkChainWidget, self).__init__(
            children=children, **kwargs)

        self.btn_submit.on_click(self._submit)

        from aiida import load_dbenv, is_dbenv_loaded
        from aiida.backends import settings
        if not is_dbenv_loaded():
            load_dbenv(profile=settings.AIIDADB_PROFILE)

    def validate(self, inputs):
        """Validate WorkChain inputs."""
        if self._validate_fn is not None:
            return self._validate_fn(inputs)

        return True

    @observe('inputs')
    def _inputs_changed(self, change):
        """Enable button if inputs validate."""
        if self.validate(change['new']):
            self.btn_submit.disabled = False
        else:
            self.btn_submit.disabled = True

    def _submit(self, change):  # pylint: disable=unused-argument
        from aiida.work import submit
        self._future = submit(self.workchain, **self.inputs)
