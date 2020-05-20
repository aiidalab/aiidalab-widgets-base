"""Widgets to work with processes."""

import os
from inspect import isclass
from time import sleep

import ipywidgets as ipw
from ipywidgets import Button, IntProgress, Layout, VBox
from IPython.display import HTML, Javascript, clear_output, display
from traitlets import Instance, observe

# AiiDA imports.
from aiida.engine import submit, Process
from aiida.orm import CalcFunctionNode, CalcJobNode, ProcessNode, WorkChainNode, WorkFunctionNode
from aiida.cmdline.utils.common import get_calcjob_report, get_workchain_report, get_process_function_report
from aiida.cmdline.utils.ascii_vis import format_call_graph

# Local imports.
from .viewers import viewer


def get_running_calcs(process):
    """Takes a process and yeilds running children calculations."""

    # If a process is a running calculation - returning it
    if issubclass(type(process), CalcJobNode) and not process.is_sealed:
        yield process

    # If the process is a running work chain - returning its children
    if issubclass(type(process), WorkChainNode) and not process.is_sealed:
        for out_link in process.get_outgoing():
            if isinstance(out_link.node, ProcessNode) and not out_link.node.is_sealed:
                yield from get_running_calcs(out_link.node)


class SubmitButtonWidget(VBox):
    """Submit button class that creates submit button jupyter widget."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self,
                 process_class,
                 input_dictionary_function,
                 description="Submit",
                 disable_after_submit=True,
                 append_output=False,
                 **kwargs):
        """Submit Button widget.

        process_class (Process): Process class to submit.

        input_dictionary_function (func): Function that generates input parameters dictionary.

        description (str): Description written on the submission button.

        disable_after_submit (bool): Whether to disable the button after the process was submitted.

        append_output (bool): Whether to clear widget output for each subsequent submission.
        """
        self.path_to_root = kwargs.get('path_to_root', '../')
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
        self.submit_out = ipw.HTML('')
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
                self.submit_out.value += """Submitted process {0}. Click
                <a href={1}aiidalab-widgets-base/process.ipynb?id={2} target="_blank">here</a>
                to follow.<br>""".format(self.process, self.path_to_root, self.process.pk)
            else:
                self.submit_out.value = """Submitted process {0}. Click
                <a href={1}aiidalab-widgets-base/process.ipynb?id={2} target="_blank">here</a>
                to follow.""".format(self.process, self.path_to_root, self.process.pk)

            for func in self._run_after_submitted:
                func(self.process)

    def on_submitted(self, function):
        """Run functions after a process has been submitted successfully."""
        self._run_after_submitted.append(function)


class ProcessInputsWidget(ipw.VBox):
    """Widget to select and show process inputs."""

    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, process=None, **kwargs):
        self.process = process
        self.output = ipw.Output()
        self.info = ipw.HTML()
        inputs_list = [(l.title(), l) for l in self.process.inputs] if self.process else []
        inputs = ipw.Dropdown(
            options=[('Select input', '')] + inputs_list,
            description='Select input:',
            style={'description_width': 'initial'},
            disabled=False,
        )
        inputs.observe(self.show_selected_input, names=['value'])
        super().__init__(children=[ipw.HBox([inputs, self.info]), self.output], **kwargs)

    def show_selected_input(self, change=None):
        """Function that displays process inputs selected in the `inputs` Dropdown widget."""
        with self.output:
            self.info.value = ''
            clear_output()
            if change['new']:
                selected_input = self.process.inputs[change['new']]
                self.info.value = "PK: {}".format(selected_input.id)
                display(viewer(selected_input))


class ProcessOutputsWidget(ipw.VBox):
    """Widget to select and show process outputs."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, process=None, **kwargs):
        self.process = process
        self.output = ipw.Output()
        self.info = ipw.HTML()
        outputs_list = [(l.title(), l) for l in self.process.outputs] if self.process else []
        outputs = ipw.Dropdown(
            options=[('Select output', '')] + outputs_list,
            label='Select output',
            description='Select outputs:',
            style={'description_width': 'initial'},
            disabled=False,
        )
        outputs.observe(self.show_selected_output, names=['value'])
        super().__init__(children=[ipw.HBox([outputs, self.info]), self.output], **kwargs)

    def show_selected_output(self, change=None):
        """Function that displays process output selected in the `outputs` Dropdown widget."""
        with self.output:
            self.info.value = ''
            clear_output()
            if change['new']:
                selected_output = self.process.outputs[change['new']]
                self.info.value = "PK: {}".format(selected_output.id)
                display(viewer(selected_output))


class ProcessFollowerWidget(ipw.VBox):
    """A Widget that follows a process until finished."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, process=None, followers=None, update_interval=0.1, path_to_root='../', **kwargs):
        """Initiate all the followers."""
        self.process = process
        self._run_after_completed = []
        self.update_interval = update_interval
        self.followers = []
        if followers is not None:
            for follower in followers:
                follower.process = self.process
                follower.path_to_root = path_to_root
                self.followers.append(ipw.VBox([
                    ipw.HTML("<h2><b>{}</b></h2>".format(follower.title)),
                    follower,
                ]))
        self.update()
        self.output = ipw.HTML()
        super(ProcessFollowerWidget, self).__init__(children=[self.output] + self.followers, **kwargs)

    def update(self):
        for follower in self.followers:
            follower.children[1].update()

    def _follow(self):
        """Periodically update all followers while the process is running."""
        while not self.process.is_sealed:
            self.update()
            sleep(self.update_interval)
        self.update()  # update the state for the last time to be 100% sure

        # Call functions to be run after the process is completed.
        for func in self._run_after_completed:
            func(self.process)

    def follow(self, detach=False):
        """Initiate following the process with or without blocking."""
        if self.process is None:
            self.output.value = """<font color="red"> ProcessFollowerWidget: process
            is set to 'None', nothing to follow. </font>"""
            return
        self.output.value = ''

        if detach:
            import threading
            update_state = threading.Thread(target=self._follow)
            update_state.start()
        else:
            self._follow()

    def on_completed(self, function):
        """Run functions after a process has been completed."""
        self._run_after_completed.append(function)


class ProcessReportWidget(ipw.HTML):
    """Widget that shows process report."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, title="Process Report", **kwargs):
        self.title = title
        self.max_depth = None
        self.indent_size = 2
        self.levelname = 'REPORT'
        self.update()
        super().__init__(**kwargs)

    def update(self):
        """Update report that is shown."""
        if self.process is None:
            return

        if isinstance(self.process, CalcJobNode):
            string = get_calcjob_report(self.process)
        elif isinstance(self.process, WorkChainNode):
            string = get_workchain_report(self.process, self.levelname, self.indent_size, self.max_depth)
        elif isinstance(self.process, (CalcFunctionNode, WorkFunctionNode)):
            string = get_process_function_report(self.process)
        else:
            string = 'Nothing to show for node type {}'.format(self.process.__class__)
        self.value = string.replace('\n', '<br/>')


class ProcessCallStackWidget(ipw.HTML):
    """Widget that shows process call stack."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, title="Process Call Stack", path_to_root='../', **kwargs):
        self.title = title
        self.path_to_root = path_to_root
        self.update()
        super().__init__(**kwargs)

    def update(self):
        """Update the call stack that is shown."""
        if self.process is None:
            return
        string = format_call_graph(self.process, info_fn=self.calc_info)
        self.value = string.replace('\n', '<br/>').replace(' ', '&nbsp;').replace('#space#', ' ')

    def calc_info(self, node):
        """Return a string with the summary of the state of a CalculationNode."""

        if not isinstance(node, ProcessNode):
            raise TypeError('Unknown type: {}'.format(type(node)))

        process_state = node.process_state.value.capitalize()
        pk = """<a#space#href={0}aiidalab-widgets-base/process.ipynb?id={1}#space#target="_blank">{1}</a>""".format(
            self.path_to_root, node.pk)

        if node.exit_status is not None:
            string = '{}<{}> {} [{}]'.format(node.process_label, pk, process_state, node.exit_status)
        else:
            string = '{}<{}> {}'.format(node.process_label, pk, process_state)

        if isinstance(node, WorkChainNode) and node.stepper_state_info:
            string += ' [{}]'.format(node.stepper_state_info)
        return string


class ProgressBarWidget(VBox):
    """A bar showing the proggress of a process."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, title="Progress Bar", **kwargs):

        self.title = title
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
        self.state = ipw.HTML(description="Calculation state:", value='Created', style={'description_width': 'initial'})
        children = [self.bar, self.state]
        super(ProgressBarWidget, self).__init__(children=children, **kwargs)

    def update(self):
        """Update the bar."""
        if self.process is None:
            return
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


class CalcJobOutputWidget(ipw.Textarea):
    """Output of a calculation."""
    calculation = Instance(CalcJobNode, allow_none=True)

    def __init__(self, **kwargs):
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
        self.output = []

        # Hack to make font monospace. As far as I am aware, currently there are no better ways.
        display(HTML("<style>textarea, input { font-family: monospace; }</style>"))

        super().__init__(**default_params)

    @observe('calculation')
    def _change_calculation(self, _=None):
        """Reset things if the observed calculation has changed."""
        self.output = []
        self.value = ''

    def update(self):
        """Update the displayed output and scroll to its end.

        NOTE: when this widgets is called by ProcessFollowerWidget in non-blocking manner
        the auto-scrolling won't work. There used to be a function for the Textarea widget,
        but it didn't work properly and got removed. For more information please visit:
        https://github.com/jupyter-widgets/ipywidgets/issues/1815"""

        if self.calculation is None:
            return

        output_file_path = None
        if 'remote_folder' in self.calculation.outputs:
            output_file_path = os.path.join(self.calculation.outputs.remote_folder.get_remote_path(),
                                            self.calculation.attributes['output_filename'])
        if output_file_path and os.path.exists(output_file_path):
            with open(output_file_path) as fobj:
                difference = fobj.readlines()[len(self.output):-1]  # Only adding the difference
                self.output += difference
                self.value += ''.join(difference)

        # Auto scroll down. Doesn't work in detached mode.
        # Also a hack as it is applied to all the textareas
        display(
            Javascript("""
            $('textarea').each(function(){
                // get the id
                var id_value = $(this).attr('id');

                if (typeof id_value !== 'undefined') {
                    // the variable is defined
                    var textarea = document.getElementById(id_value);
                    textarea.scrollTop = textarea.scrollHeight;
                }   
            });"""))


class RunningCalcJobOutputWidget(ipw.VBox):
    """Show an output of selected running child calculation."""
    process = Instance(ProcessNode, allow_none=True)

    def __init__(self, title="Running Job Output", **kwargs):
        self.title = title
        self.selection = ipw.Dropdown(description="Select calculation:",
                                      options={p.id: p for p in get_running_calcs(self.process)},
                                      style={'description_width': 'initial'})
        self.output = CalcJobOutputWidget()
        self.update()
        super().__init__(children=[self.selection, self.output], **kwargs)

    def update(self):
        """Update the displayed output."""
        if self.process is None:
            return
        with self.hold_trait_notifications():
            old_label = self.selection.label
            self.selection.options = {str(p.id): p for p in get_running_calcs(self.process)}
            # If the selection remains the same.
            if old_label in self.selection.options:
                self.label = old_label  # After changing options trait, the label and value traits might change as well.
            # If selection has changed
            else:
                self.output.calculation = self.selection.value
        self.output.update()
