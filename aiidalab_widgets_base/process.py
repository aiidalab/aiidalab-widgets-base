"""Widgets to work with processes."""

# pylint: disable=no-self-use
# Built-in imports
from __future__ import annotations

import inspect
import sys
import threading
import warnings

import ipywidgets as ipw
import traitlets as tl
from aiida import engine, orm

# Local imports.
from .nodes import NodesTreeWidget
from .utils import exceptions


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
                <a href={self.path_to_root}home/process.ipynb?id={self.process.pk}
                target="_blank">here</a> to follow.<br>"""
            else:
                self.submit_out.value = f"""Submitted process {self.process}. Click
                <a href={self.path_to_root}home/process.ipynb?id={self.process.pk}
                target="_blank">here</a> to follow."""

            for func in self._run_after_submitted:
                func(self.process)

    def on_submitted(self, function):
        """Run functions after a process has been submitted successfully."""
        self._run_after_submitted.append(function)


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

        self.log_widget: ipw.Output | None = kwargs.pop("log_widget", None)

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
                    if self.log_widget:
                        with self.log_widget:
                            traceback.print_exc(file=sys.stdout)
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
