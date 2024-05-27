"""Widgets to work with processes."""

# pylint: disable=no-self-use
# Built-in imports
from __future__ import annotations

import inspect
import os
import threading
import time
import traceback
import uuid
import warnings

import ipywidgets as ipw
import traitlets as tl
from aiida import engine, orm
from aiida.cmdline.utils.ascii_vis import format_call_graph
from aiida.cmdline.utils.common import (
    get_calcjob_report,
    get_process_function_report,
    get_workchain_report,
)
from aiida.common.exceptions import NotExistentAttributeError
from aiida.tools.query.calculation import CalculationQueryBuilder
from IPython.display import HTML, Javascript, clear_output, display

# Local imports.
from .nodes import NodesTreeWidget
from .utils import exceptions
from .viewers import viewer


def get_running_calcs(process):
    """Takes a process and yeilds running children calculations."""

    # If a process is a running calculation - returning it
    if issubclass(type(process), orm.CalcJobNode) and not process.is_sealed:
        yield process

    # If the process is a running work chain - returning its children
    elif issubclass(type(process), orm.WorkChainNode) and not process.is_sealed:
        for out_link in process.get_outgoing():
            if (
                isinstance(out_link.node, orm.ProcessNode)
                and not out_link.node.is_sealed
            ):
                yield from get_running_calcs(out_link.node)


class SubmitButtonWidget(ipw.VBox):
    """Submit button class that creates submit button jupyter widget."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        process_class,
        inputs_generator,
        description="Submit",
        disable_after_submit=True,
        append_output=False,
        **kwargs,
    ):
        """Submit Button widget.

        process_class (Process): Process class to submit.

        inputs_generator (func): Function that returns inputs dictionary or inputs builder.

        description (str): Description written on the submission button.

        disable_after_submit (bool): Whether to disable the button after the process was submitted.

        append_output (bool): Whether to clear widget output for each subsequent submission.
        """

        self.path_to_root = kwargs.get("path_to_root", "../")
        if inspect.isclass(process_class) and issubclass(process_class, engine.Process):
            self._process_class = process_class
        else:
            raise ValueError(
                f"process_class argument must be a sublcass of {engine.Process}, got {process_class}"
            )

        # Checking if the inputs generator is callable
        if callable(inputs_generator):
            self.inputs_generator = inputs_generator
        else:
            raise TypeError(
                "The `inputs_generator` argument must be a function that "
                f"returns input dictionary, got {type(inputs_generator)}"
            )

        self.disable_after_submit = disable_after_submit
        self.append_output = append_output

        self.btn_submit = ipw.Button(description=description, disabled=False)
        self.btn_submit.on_click(self.on_btn_submit_press)
        self.submit_out = ipw.HTML("")
        self._run_after_submitted = []

        super().__init__(children=[self.btn_submit, self.submit_out])

    def on_click(self, function):
        self.btn_submit.on_click(function)

    def on_btn_submit_press(self, _=None):
        """When submit button is pressed."""

        if not self.append_output:
            self.submit_out.value = ""

        inputs = self.inputs_generator()
        if inputs is None:
            if self.append_output:
                self.submit_out.value += (
                    "SubmitButtonWidget: did not recieve the process inputs.<br>"
                )
            else:
                self.submit_out.value = (
                    "SubmitButtonWidget: did not recieve the process inputs."
                )
        else:
            if self.disable_after_submit:
                self.btn_submit.disabled = True
            if isinstance(inputs, engine.ProcessBuilder):
                self.process = engine.submit(inputs)
            else:
                self.process = engine.submit(self._process_class, **inputs)

            if self.append_output:
                self.submit_out.value += f"""Submitted process {self.process}. Click
                <a href={self.path_to_root}aiidalab-widgets-base/notebooks/process.ipynb?id={self.process.pk}
                target="_blank">here</a> to follow.<br>"""
            else:
                self.submit_out.value = f"""Submitted process {self.process}. Click
                <a href={self.path_to_root}aiidalab-widgets-base/notebooks/process.ipynb?id={self.process.pk}
                target="_blank">here</a> to follow."""

            for func in self._run_after_submitted:
                func(self.process)

    def on_submitted(self, function):
        """Run functions after a process has been submitted successfully."""
        self._run_after_submitted.append(function)


class ProcessInputsWidget(ipw.VBox):
    """Widget to select and show process inputs."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(self, process=None, **kwargs):
        self.process = process
        self.output = ipw.Output()
        self.info = ipw.HTML()

        self.flat_mapping = self.generate_flat_mapping(process=process) or {}
        inputs_list = list(self.flat_mapping.items())

        self._inputs = ipw.Dropdown(
            options=[("Select input", ""), *inputs_list],
            description="Select input:",
            style={"description_width": "initial"},
            disabled=False,
        )
        self._inputs.observe(self.show_selected_input, names=["value"])
        super().__init__(
            children=[ipw.HBox([self._inputs, self.info]), self.output], **kwargs
        )

    def generate_flat_mapping(
        self, process: orm.ProcessNode | None = None
    ) -> None | dict[str, str]:
        """Generate a dict of input to node uuid mapping.

        If the input port is a namespace, it will further parse the namespace and attach the entity the
        `<namespace>.<childnamespace>.<node_name>` format.

        :param process: Process node.
        :return: Dict of flatten embed key name to node UUID."""
        from collections.abc import Mapping

        from aiida.common.links import LinkType

        if process is None:
            return None

        nested_dict = process.base.links.get_incoming(
            link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK)
        ).nested()

        def flatten(d, parent_key="", sep="."):
            items = []
            for key, value in d.items():
                new_key = parent_key + sep + key if parent_key else key
                if isinstance(value, Mapping):
                    items.extend(flatten(value, new_key, sep=sep).items())
                else:
                    items.append((new_key, value.uuid))
            return dict(items)

        options_map = flatten(nested_dict)

        return options_map

    def show_selected_input(self, change=None):
        """Function that displays process inputs selected in the `inputs` Dropdown widget."""
        with self.output:
            self.info.value = ""
            clear_output()
            if change["new"]:
                selected_input = orm.load_node(change["new"])
                self.info.value = f"PK: {selected_input.pk}"
                display(viewer(selected_input))


class ProcessOutputsWidget(ipw.VBox):
    """Widget to select and show process outputs."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(self, process=None, **kwargs):
        self.process = process
        self.output = ipw.Output()
        self.info = ipw.HTML()
        outputs_list = (
            [(output.title(), output) for output in self.process.outputs]
            if self.process
            else []
        )
        outputs = ipw.Dropdown(
            options=[("Select output", ""), *outputs_list],
            label="Select output",
            description="Select outputs:",
            style={"description_width": "initial"},
            disabled=False,
        )
        outputs.observe(self.show_selected_output, names=["value"])
        super().__init__(
            children=[ipw.HBox([outputs, self.info]), self.output], **kwargs
        )

    def show_selected_output(self, change=None):
        """Function that displays process output selected in the `outputs` Dropdown widget."""
        with self.output:
            self.info.value = ""
            clear_output()
            if change["new"]:
                selected_output = self.process.outputs[change["new"]]
                self.info.value = f"PK: {selected_output.pk}"
                display(viewer(selected_output))


class ProcessFollowerWidget(ipw.VBox):
    """A Widget that follows a process until finished."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(
        self,
        process=None,
        followers=None,
        update_interval=1.0,
        path_to_root="../",
        **kwargs,
    ):
        """Initiate all the followers."""
        self._monitor = None

        self.process = process
        self._run_after_completed = []
        self.update_interval = update_interval
        self.followers = []
        if followers is not None:
            for follower in followers:
                follower.process = self.process
                follower.path_to_root = path_to_root
                self.followers.append(
                    ipw.VBox(
                        [
                            ipw.HTML(f"<h2><b>{follower.title}</b></h2>"),
                            follower,
                        ]
                    )
                )
        self.output = ipw.HTML()
        super().__init__(children=[self.output, *self.followers], **kwargs)
        self.update()

    def update(self):
        for follower in self.followers:
            follower.children[1].update()

    def follow(self, detach=False):
        """Initiate following the process with or without blocking."""
        if self.process is None:
            self.output.value = """<font color="red"> ProcessFollowerWidget: process
            is set to 'None', nothing to follow. </font>"""
            return
        self.output.value = ""

        if self._monitor is None:
            self._monitor = ProcessMonitor(
                callbacks=[self.update],
                on_sealed=self._run_after_completed,
                timeout=self.update_interval,
            )
            ipw.dlink(
                (self, "process"), (self._monitor, "value"), transform=lambda x: x.uuid
            )

        if not detach:
            self._monitor.join()

    def on_completed(self, function):
        """Run functions after a process has been completed."""
        if self._monitor is not None:
            raise exceptions.CantRegisterCallbackError(function)
        self._run_after_completed.append(function)


class ProcessReportWidget(ipw.HTML):
    """Widget that shows process report."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)
    value = tl.Unicode(allow_none=True)

    def __init__(self, title="Process Report", **kwargs):
        self.title = title
        self.max_depth = None
        self.indent_size = 2
        self.levelname = "REPORT"
        super().__init__(**kwargs)
        self.update()

    def update(self):
        """Update report that is shown."""
        if self.process is None:
            return

        if isinstance(self.process, orm.CalcJobNode):
            string = get_calcjob_report(self.process)
        elif isinstance(self.process, orm.WorkChainNode):
            string = get_workchain_report(
                self.process, self.levelname, self.indent_size, self.max_depth
            )
        elif isinstance(self.process, (orm.CalcFunctionNode, orm.WorkFunctionNode)):
            string = get_process_function_report(self.process)
        else:
            string = f"Nothing to show for node type {self.process.__class__}"
        self.value = string.replace("\n", "<br/>")


class ProcessCallStackWidget(ipw.HTML):
    """Widget that shows process call stack."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(self, title="Process Call Stack", path_to_root="../", **kwargs):
        self.title = title
        self.path_to_root = path_to_root
        super().__init__(**kwargs)
        self.update()

    def update(self):
        """Update the call stack that is shown."""
        if self.process is None:
            return
        string = format_call_graph(self.process, info_fn=self.calc_info)
        self.value = (
            string.replace("\n", "<br/>").replace(" ", "&nbsp;").replace("#space#", " ")
        )

    # The third parameter 'call_link_label', added in AiiDA 2.4, is not used here.
    # https://github.com/aiidateam/aiida-core/pull/6056
    def calc_info(self, node, _=False):
        """Return a string with the summary of the state of a CalculationNode."""

        if not isinstance(node, orm.ProcessNode):
            raise TypeError(f"Unknown type: {type(node)}")

        process_state = node.process_state.value.capitalize()
        pk = f"""<a#space#href={self.path_to_root}aiidalab-widgets-base/notebooks/process.ipynb?id={node.pk}#space#target="_blank">{node.pk}</a>"""

        if node.exit_status is not None:
            string = f"{node.process_label}<{pk}> {process_state} [{node.exit_status}]"
        else:
            string = f"{node.process_label}<{pk}> {process_state}"

        if isinstance(node, orm.WorkChainNode) and node.stepper_state_info:
            string += f" [{node.stepper_state_info}]"
        return string


class ProgressBarWidget(ipw.VBox):
    """A bar showing the proggress of a process."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(self, title="Progress Bar", **kwargs):
        """Initialize ProgressBarWidget."""

        self.title = title
        self.correspondance = {
            "created": 0,
            "running": 1,
            "waiting": 1,
            "killed": 2,
            "excepted": 2,
            "finished": 2,
        }
        self.progress_bar = ipw.IntProgress(
            value=0,
            min=0,
            max=2,
            description="Progress:",
            bar_style="warning",  # 'success', 'info', 'warning', 'danger' or ''
            orientation="horizontal",
            layout={"width": "800px"},
        )
        self.state = ipw.HTML(
            description="Calculation state:",
            value="Created",
            style={"description_width": "initial"},
        )
        super().__init__(children=[self.progress_bar, self.state], **kwargs)
        self.update()

    def update(self):
        """Update the bar."""
        if self.process is None:
            return
        self.progress_bar.value = self.correspondance[self.current_state]
        if self.current_state == "finished":
            self.progress_bar.bar_style = "success"
        elif self.current_state in ["killed", "excepted"]:
            self.progress_bar.bar_style = "danger"
        else:
            self.progress_bar.bar_style = "info"
        self.state.value = self.current_state.capitalize()

    @property
    def current_state(self):
        return self.process.process_state.value


class CalcJobOutputWidget(ipw.Textarea):
    """Output of a calculation."""

    calculation = tl.Instance(orm.CalcJobNode, allow_none=True)

    def __init__(self, **kwargs):
        default_params = {
            "value": "",
            "placeholder": "Calculation output will appear here",
            "description": "Calculation output:",
            "layout": {"width": "900px", "height": "300px"},
            "disabled": False,
            "style": {"description_width": "initial"},
        }
        default_params.update(kwargs)
        self.output = []

        # Hack to make font monospace. As far as I am aware, currently there are no better ways.
        display(HTML("<style>textarea, input { font-family: monospace; }</style>"))

        super().__init__(**default_params)

    @tl.observe("calculation")
    def _change_calculation(self, _=None):
        """Reset things if the observed calculation has changed."""
        self.output = []
        self.value = ""

    def update(self):
        """Update the displayed output and scroll to its end.

        NOTE: when this widgets is called by ProcessFollowerWidget in non-blocking manner
        the auto-scrolling won't work. There used to be a function for the Textarea widget,
        but it didn't work properly and got removed. For more information please visit:
        https://github.com/jupyter-widgets/ipywidgets/issues/1815"""

        if self.calculation is None:
            return

        try:
            output_file_path = os.path.join(
                self.calculation.outputs.remote_folder.get_remote_path(),
                self.calculation.base.attributes.get("output_filename"),
            )
        except KeyError:
            self.placeholder = (
                "The `output_filename` attribute is not set for "
                f"{self.calculation.process_class}. Nothing to show."
            )
        except NotExistentAttributeError:
            self.placeholder = (
                "The object `remote_folder` was not found among the process outputs. "
                "Nothing to show."
            )
        else:
            if os.path.exists(output_file_path):
                with open(output_file_path) as fobj:
                    difference = fobj.readlines()[
                        len(self.output) : -1
                    ]  # Only adding the difference
                    self.output += difference
                    self.value += "".join(difference)

        # Auto scroll down. Doesn't work in detached mode.
        # Also a hack as it is applied to all the textareas
        display(
            Javascript(
                """
            $('textarea').each(function(){
                // get the id
                var id_value = $(this).attr('id');

                if (typeof id_value !== 'undefined') {
                    // the variable is defined
                    var textarea = document.getElementById(id_value);
                    textarea.scrollTop = textarea.scrollHeight;
                }
            });"""
            )
        )


class RunningCalcJobOutputWidget(ipw.VBox):
    """Show an output of selected running child calculation."""

    process = tl.Instance(orm.ProcessNode, allow_none=True)

    def __init__(self, title="Running Job Output", **kwargs):
        self.title = title
        self.selection = ipw.Dropdown(
            description="Select calculation:",
            options=tuple((p.pk, p) for p in get_running_calcs(self.process)),
            style={"description_width": "initial"},
        )
        self.output = CalcJobOutputWidget()
        super().__init__(children=[self.selection, self.output], **kwargs)
        self.update()

    def update(self):
        """Update the displayed output."""
        if self.process is None:
            return
        with self.hold_trait_notifications():
            old_label = self.selection.label
            self.selection.options = tuple(
                (str(p.pk), p) for p in get_running_calcs(self.process)
            )
            # If the selection remains the same.
            if old_label in self.selection.options:
                self.label = old_label  # After changing options trait, the label and value traits might change as well.
            # If selection has changed
            else:
                self.output.calculation = self.selection.value
        self.output.update()


class ProcessListWidget(ipw.VBox):
    """List of AiiDA processes.

    past_days (int): Sumulations that were submitted in the last `past_days`.

    incoming_node (str): Trait that takes node uuid that must
    be among the input nodes of the process of interest.

    outgoing_node (str): Trait that takes node uuid that must
    be among the output nodes of the process of interest.

    process_states (list): List of allowed process states.

    process_label (str): Show process states of type `process_label`.

    description_contains (str): string that should be present in the description of a process node.

    """

    past_days = tl.Int(7)
    incoming_node = tl.Unicode(allow_none=True)
    outgoing_node = tl.Unicode(allow_none=True)
    process_states = tl.List()
    process_label = tl.Unicode(allow_none=True)
    description_contains = tl.Unicode(allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):
        self.path_to_root = path_to_root
        self.table = ipw.HTML()
        self.output = ipw.HTML()
        update_button = ipw.Button(description="Update now")
        update_button.on_click(self.update)
        super().__init__(
            children=[ipw.HBox([self.output, update_button]), self.table], **kwargs
        )
        self.update()

    def update(self, _=None):
        """Perform the query."""
        import pandas as pd

        pd.set_option("max_colwidth", 40)
        # Here we are defining properties of 'df' class (specified while exporting pandas table into html).
        # Since the exported object is nothing more than HTML table, all 'standard' HTML table settings
        # can be applied to it as well.
        # For more information on how to controle the table appearance please visit:
        # https://css-tricks.com/complete-guide-table-element/
        self.table.value = """
        <style>
            .df { border: none; }
            .df tbody tr:nth-child(odd) { background-color: #e5e7e9; }
            .df tbody tr:nth-child(odd):hover { background-color:   #f5b7b1; }
            .df tbody tr:nth-child(even):hover { background-color:  #f5b7b1; }
            .df tbody td { min-width: 150px; text-align: center; border: none }
            .df th { text-align: center; border: none;  border-bottom: 1px solid black;}
        </style>
        """
        builder = CalculationQueryBuilder()
        filters = builder.get_filters(
            all_entries=False,
            process_state=self.process_states,
            process_label=self.process_label,
            exit_status=None,
            failed=None,
        )
        relationships = {}
        if self.incoming_node:
            relationships = {
                **relationships,
                **{"with_outgoing": orm.load_node(self.incoming_node)},
            }

        if self.outgoing_node:
            relationships = {
                **relationships,
                **{"with_incoming": orm.load_node(self.outgoing_node)},
            }

        query_set = builder.get_query_set(
            filters=filters,
            past_days=None if self.past_days < 0 else self.past_days,
            order_by={"ctime": "desc"},
            relationships=relationships,
        )
        projected = builder.get_projected(
            query_set,
            projections=[
                "pk",
                "ctime",
                "process_label",
                "state",
                "process_status",
                "description",
            ],
        )
        dataf = pd.DataFrame(projected[1:], columns=projected[0])

        # Keep only process that contain the requested string in the description.
        if self.description_contains:
            dataf = dataf[dataf.Description.str.contains(self.description_contains)]

        self.output.value = f"{len(dataf)} processes shown"

        # Add HTML links.
        dataf["PK"] = dataf["PK"].apply(
            lambda x: f"""<a href={self.path_to_root}aiidalab-widgets-base/notebooks/process.ipynb?id={x} target="_blank">{x}</a>"""
        )
        self.table.value += dataf.to_html(classes="df", escape=False, index=False)

    @tl.validate("incoming_node")
    def _validate_incoming_node(self, provided):
        """Validate incoming node."""
        node_uuid = provided["value"]
        try:
            _ = uuid.UUID(node_uuid, version=4)
        except ValueError:
            self.output.value = f"""'<span style="color:red">{node_uuid}</span>'
            is not a valid UUID."""
        else:
            return node_uuid

    @tl.validate("outgoing_node")
    def _validate_outgoing_node(self, provided):
        """Validate outgoing node. The function orm.load_node takes care of managing ids and uuids."""
        node_uuid = provided["value"]
        try:
            _ = uuid.UUID(node_uuid, version=4)
        except ValueError:
            self.output.value = f"""'<span style="color:red">{node_uuid}</span>'
            is not a valid UUID."""
        else:
            return node_uuid

    @tl.default("process_label")
    def _default_process_label(self):
        return None

    @tl.validate("process_label")
    def _validate_process_label(self, provided):
        if provided["value"]:
            return provided["value"]
        return None

    def _follow(self, update_interval):
        while True:
            self.update()
            time.sleep(update_interval)

    def start_autoupdate(self, update_interval=10):
        import threading

        update_state = threading.Thread(target=self._follow, args=(update_interval,))
        update_state.start()


class ProcessMonitor(tl.HasTraits):
    """Monitor a process and execute callback functions at specified intervals."""

    value = tl.Unicode(allow_none=True)

    def __init__(self, callbacks=None, on_sealed=None, timeout=None, **kwargs):
        self.callbacks = [] if callbacks is None else list(callbacks)
        self.on_sealed = [] if on_sealed is None else list(on_sealed)
        self.timeout = 1.0 if timeout is None else timeout

        self._monitor_thread = None
        self._monitor_thread_stop = threading.Event()
        self._monitor_thread_lock = threading.Lock()

        super().__init__(**kwargs)

    @tl.observe("value")
    def _observe_process(self, change):
        """When the value (process uuid) is changed, stop the previous
        monitor if exist. Start a new one in thread."""
        process_uuid = change["new"]

        # stop thread (if running)
        if self._monitor_thread is not None:
            with self._monitor_thread_lock:
                self._monitor_thread_stop.set()
                self._monitor_thread.join()

        if process_uuid is None:
            return

        with self._monitor_thread_lock:
            self._monitor_thread_stop.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_process, args=(process_uuid,)
            )
            self._monitor_thread.start()

    def _monitor_process(self, process_uuid):
        assert process_uuid is not None
        process = orm.load_node(process_uuid)

        disabled_funcs = set()

        def _run(funcs):
            for func in funcs:
                # skip all functions that had previously raised an exception
                if func in disabled_funcs:
                    continue

                try:
                    if len(inspect.signature(func).parameters) > 0:
                        func(process_uuid)
                    else:
                        func()
                except Exception:
                    warnings.warn(
                        f"WARNING: The callback function {func.__name__!r} was disabled due to an error:\n{traceback.format_exc()}",
                        stacklevel=2,
                    )
                    disabled_funcs.add(func)

        while not process.is_sealed:
            _run(self.callbacks)

            if self._monitor_thread_stop.wait(timeout=self.timeout):
                break  # thread was signaled to be stopped

        # Final update:
        _run(self.callbacks)

        # Run special 'on_sealed' callback functions in case that process is sealed.
        if process.is_sealed:
            _run(self.on_sealed)

    def join(self):
        if self._monitor_thread is not None:
            self._monitor_thread.join()


class ProcessNodesTreeWidget(ipw.VBox):
    """A tree widget for the structured representation of a process graph."""

    value = tl.Unicode(allow_none=True)
    selected_nodes = tl.Tuple(read_only=True).tag(trait=tl.Instance(orm.Node))

    def __init__(self, title="Process Tree", **kwargs):
        self.title = title  # needed for ProcessFollowerWidget

        self._tree = NodesTreeWidget()
        self._tree.observe(self._observe_tree_selected_nodes, ["selected_nodes"])
        super().__init__(children=[self._tree], **kwargs)
        self.update()

    def _observe_tree_selected_nodes(self, change):
        self.set_trait("selected_nodes", change["new"])

    def update(self, _=None):
        self._tree.update()

    @tl.observe("value")
    def _observe_process(self, change):
        process_uuid = change["new"]
        if process_uuid:
            process = orm.load_node(process_uuid)
            self._tree.nodes = [process]
            self._tree.find_node(process.pk).selected = True
        else:
            self._tree.nodes = []
