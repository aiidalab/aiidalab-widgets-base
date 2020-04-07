"""Widgets to work with processes."""

import os
from inspect import isclass
from ipywidgets import Button, HTML, IntProgress, Layout, Textarea, VBox
from traitlets import Instance

# AiiDA imports
from aiida.engine import submit, Process
from aiida.orm import CalcJobNode, ProcessNode, WorkChainNode


def get_running_calcs(process):
    """Takes a process and returns a list of running calculations. The running calculations
    can be either the process itself or its running children."""

    # If a process is a running calculation - returning it
    if issubclass(type(process), CalcJobNode) and not process.is_sealed:
        return [process]

    # If the process is a running work chain - returning its children
    if issubclass(type(process), WorkChainNode) and not process.is_sealed:
        calcs = []
        for link in process.get_outgoing():
            if issubclass(type(link.node), ProcessNode) and not link.node.is_sealed:
                calcs += get_running_calcs(link.node)
        return calcs
    # if it is neither calculation, nor work chain - returninng None
    return []


class SubmitButtonWidget(VBox):
    """Submit button class that creates submit button jupyter widget."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self,
                 process_class,
                 input_dictionary_function,
                 description="Submit",
                 disable_after_submit=True,
                 append_output=False):
        """Submit Button widget.

        process_class (Process): Process class to submit.

        input_dictionary_function (func): Function that generates input parameters dictionary.

        description (str): Description written on the submission button.

        disable_after_submit (bool): Whether to disable the button after the process was submitted.

        append_output (bool): Whether to clear widget output for each subsequent submission.
        """

        if isclass(process_class) and issubclass(process_class, Process):
            self._process_class = process_class
        else:
            raise ValueError("process_class argument must be a sublcass of {}, got {}".format(Process, process_class))

        if callable(input_dictionary_function):
            self.input_dictionary_function = input_dictionary_function
        else:
            raise ValueError(
                "input_dictionary_function argument must be a function that returns input dictionary, got {}".format(
                    input_dictionary_function))

        self.disable_after_submit = disable_after_submit
        self.append_output = append_output

        self.btn_submit = Button(description=description, disabled=False)
        self.btn_submit.on_click(self.on_btn_submit_press)
        self.submit_out = HTML('')
        children = [
            self.btn_submit,
            self.submit_out,
        ]

        self._run_after_submitted = []

        super(SubmitButtonWidget, self).__init__(children=children)

    def on_click(self, function):
        self.btn_submit.on_click(function)

    def on_btn_submit_press(self, _=None):
        """When submit button is pressed."""

        if not self.append_output:
            self.submit_out.value = ''

        input_dict = self.input_dictionary_function()
        if input_dict is None:
            if self.append_output:
                self.submit_out.value += "SubmitButtonWidget: did not recieve input dictionary.<br>"
            else:
                self.submit_out.value = "SubmitButtonWidget: did not recieve input dictionary."
        else:
            self.btn_submit.disabled = self.disable_after_submit
            self.process = submit(self._process_class, **input_dict)

            if self.append_output:
                self.submit_out.value += "Submitted process {}<br>".format(self.process)
            else:
                self.submit_out.value = "Submitted process {}".format(self.process)

            for func in self._run_after_submitted:
                func(self.process)

    def on_submitted(self, function):
        """Run functions after a process has been submitted successfully."""
        self._run_after_submitted.append(function)


class ProcessFollowerWidget(VBox):
    """A Widget that follows a process until finished."""

    def __init__(self, process, followers=None, update_interval=0.1, **kwargs):
        """Initiate all the followers."""
        if not isinstance(process, ProcessNode):
            raise TypeError("Expecting an object of type {}, got {}".format(ProcessNode, type(process)))
        self.process = process
        self._run_after_completed = []
        self.update_interval = update_interval
        self.followers = []
        if followers is not None:
            for follower in followers:
                self.followers.append(follower(process=process))
        self.update()
        super(ProcessFollowerWidget, self).__init__(children=self.followers, **kwargs)

    def update(self):
        for follower in self.followers:
            follower.update()

    def _follow(self):
        """The loop that will update all the followers untill the process is running."""
        from time import sleep
        while not self.process.is_sealed:
            self.update()
            sleep(self.update_interval)
        self.update()  # update the state for the last time to be 100% sure

        # Call functions to be run after the process is completed.
        for func in self._run_after_completed:
            func(self.process)

    def follow(self, detach=False):
        """Follow the process in blocking or non-blocking manner."""
        if detach:
            import threading
            update_state = threading.Thread(target=self._follow)
            update_state.start()
        else:
            self._follow()

    def on_completed(self, function):
        """Run functions after a process has been completed."""
        self._run_after_completed.append(function)


class ProgressBarWidget(VBox):
    """A bar showing the proggress of a process."""

    def __init__(self, process, **kwargs):

        self.process = process
        self.correspondance = {
            "created": 0,
            "running": 1,
            "waiting": 1,
            "killed": 2,
            "excepted": 2,
            "finished": 2,
        }
        self.bar = IntProgress(  # pylint: disable=blacklisted-name
            value=0,
            min=0,
            max=2,
            step=1,
            description='Progress:',
            bar_style='warning',  # 'success', 'info', 'warning', 'danger' or ''
            orientation='horizontal',
            layout=Layout(width="800px"))
        self.state = HTML(description="Calculation state:", value='Created', style={'description_width': 'initial'})
        children = [self.bar, self.state]
        super(ProgressBarWidget, self).__init__(children=children, **kwargs)

    def update(self):
        """Update the bar."""
        self.bar.value = self.correspondance[self.current_state]
        if self.current_state == 'finished':
            self.bar.bar_style = 'success'
        elif self.current_state in ["killed", "excepted"]:
            self.bar.bar_style = 'danger'
        else:
            self.bar.bar_style = 'info'
        self.state.value = self.current_state.capitalize()

    @property
    def current_state(self):
        return self.process.process_state.value


class RunningCalcJobOutputWidget(Textarea):
    """Output of a currently running calculation or one of work chain's running child."""

    def __init__(self, process, **kwargs):
        self.main_process = process
        default_params = {
            "value": "",
            "placeholder": "Calculation output will appear here",
            "description": "Calculation output:",
            "layout": {
                'width': "900px",
                'height': '300px'
            },
            "disabled": False,
            "style": {
                'description_width': 'initial'
            }
        }
        default_params.update(kwargs)
        self.previous_calc_id = 0
        self.output = []
        super(RunningCalcJobOutputWidget, self).__init__(**default_params)

    def update(self):
        """Update the displayed output."""
        calcs = get_running_calcs(self.main_process)
        if calcs:
            for calc in calcs:
                if calc.id == self.previous_calc_id:
                    break
            else:
                self.output = []
                self.previous_calc_id = calc.id
                self.value = ''
            if 'remote_folder' in calc.outputs:
                f_path = os.path.join(calc.outputs.remote_folder.get_remote_path(), calc.attributes['output_filename'])
                if os.path.exists(f_path):
                    with open(f_path) as fobj:
                        self.output += fobj.readlines()[len(self.output):-1]
                        self.value = ''.join(self.output)
