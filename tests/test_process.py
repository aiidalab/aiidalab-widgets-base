import pytest
from aiida import engine, orm
from aiida.workflows.arithmetic.multiply_add import MultiplyAddWorkChain

import aiidalab_widgets_base as awb


@pytest.mark.usefixtures("aiida_profile_clean")
def test_submit_button_widget(multiply_add_process_builder_ready):
    """Test SubmitButtonWidget with a simple `WorkChainNode`"""

    def hook(_=None):
        pass

    def return_inputs():
        return multiply_add_process_builder_ready

    widget = awb.SubmitButtonWidget(
        process_class=MultiplyAddWorkChain, inputs_generator=return_inputs
    )

    widget.on_submitted(hook)

    assert widget.process is None  # The process is not yet submitted.

    # Simulate the click on the button.
    widget.on_btn_submit_press()
    assert widget.process is not None
    assert isinstance(widget.process, orm.WorkChainNode)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_inputs_widget(generate_calc_job_node):
    """Test ProcessInputWidget with a simple `CalcJobNode`"""

    process = generate_calc_job_node(
        inputs={
            "parameters": orm.Int(1),
            "nested": {
                "inner": orm.Int(2),
            },
        }
    )

    # Test the widget can be instantiated with empty inputs
    process_input_widget = awb.ProcessInputsWidget()

    process_input_widget = awb.ProcessInputsWidget(process=process)
    input_dropdown = process_input_widget._inputs

    assert "parameters" in [key for key, _ in input_dropdown.options]
    assert "nested.inner" in [key for key, _ in input_dropdown.options]

    # select the nested input from dropdown and check that the value is displayed)
    uuid = dict(input_dropdown.options)["nested.inner"]
    input_dropdown.value = uuid

    selected_input = orm.load_node(uuid)

    assert process_input_widget.info.value == f"PK: {selected_input.pk}"


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_outputs_widget(multiply_add_completed_workchain):
    """Test ProcessOutputWidget with a simple `WorkChainNode`"""
    # Test the widget can be instantiated with empty inputs
    widget = awb.ProcessOutputsWidget()

    # Test the widget can be instantiated with a process
    widget = awb.ProcessOutputsWidget(process=multiply_add_completed_workchain)

    # Simulate output selection.
    widget.show_selected_output(change={"new": "result"})


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_follower_widget(multiply_add_process_builder_ready, daemon_client):
    """Test ProcessFollowerWidget with a simple `WorkChainNode`"""
    # Test the widget can be instantiated with empty inputs
    widget = awb.ProcessFollowerWidget()

    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    # Test the widget can be instantiated with a process
    widget = awb.ProcessFollowerWidget(process=process)

    daemon_client.start_daemon()

    # Follow the process till it is completed.
    widget.follow()

    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_report_widget(
    multiply_add_process_builder_ready, daemon_client, await_for_process_completeness
):
    """Test ProcessReportWidget with a simple `WorkChainNode`"""
    # Test the widget can be instantiated with empty inputs
    awb.ProcessReportWidget()

    # Stopping the daemon and submitting the process.
    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    # Test the widget can be instantiated with a process
    widget = awb.ProcessReportWidget(process=process)
    assert (
        widget.value == "No log messages recorded for this entry"
    )  # No report produced yet.

    # Starting the daemon and waiting for the process to complete.
    daemon_client.start_daemon()
    await_for_process_completeness(process)

    widget.update()
    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_call_stack_widget(
    multiply_add_process_builder_ready, daemon_client, await_for_process_completeness
):
    """Test ProcessCallStackWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base.process import ProcessCallStackWidget

    # Test the widget can be instantiated with empty inputs
    ProcessCallStackWidget()

    # Stopping the daemon and submitting the process.
    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    # Test the widget can be instantiated with a process
    widget = ProcessCallStackWidget(process=process)
    assert widget.value.endswith("Created")

    # Starting the daemon and waiting for the process to complete.
    daemon_client.start_daemon()
    await_for_process_completeness(process)

    widget.update()
    assert "ArithmeticAddCalculation" in widget.value
    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_progress_bar_widget(
    multiply_add_process_builder_ready, daemon_client, await_for_process_completeness
):
    """Test ProgressBarWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base import ProgressBarWidget

    # Test the widget can be instantiated with empty inputs
    ProgressBarWidget()

    # Stopping the daemon and submitting the process.
    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    # Test the widget can be instantiated with a process
    widget = ProgressBarWidget(process=process)
    assert widget.state.value == "Created"

    # Starting the daemon and waiting for the process to complete.
    daemon_client.start_daemon()
    await_for_process_completeness(process)

    widget.update()
    assert widget.state.value == "Finished"
    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_calcjob_output_widget(generate_calc_job_node):
    """Test CalcJobOutputWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base.process import CalcJobOutputWidget

    process = generate_calc_job_node(
        inputs={
            "parameters": orm.Int(1),
            "nested": {
                "inner": orm.Int(2),
            },
        }
    )
    # Test the widget can be instantiated with empty inputs
    CalcJobOutputWidget()

    # Test the widget can be instantiated with a process
    CalcJobOutputWidget(calculation=process)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_running_calcjob_output_widget(generate_calc_job_node):
    """Test RunningCalcJobOutputWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base.process import RunningCalcJobOutputWidget

    process = generate_calc_job_node(
        inputs={
            "parameters": orm.Int(1),
            "nested": {
                "inner": orm.Int(2),
            },
        }
    )

    widget = RunningCalcJobOutputWidget()
    widget.process = process


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_list_widget(multiply_add_completed_workchain):
    """Test ProcessListWidget with a simple `WorkChainNode`"""
    awb.ProcessListWidget()


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_monitor(
    multiply_add_process_builder_ready, daemon_client, await_for_process_completeness
):
    """Test ProcessMonitor with a simple `WorkChainNode`"""
    awb.ProcessMonitor()

    # Stopping the daemon and submitting the process.
    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    test_variable = False

    def f():
        nonlocal test_variable
        test_variable = True

    widget = awb.ProcessMonitor(value=process.uuid, callbacks=[f])

    # Starting the daemon and waiting for the process to complete.
    daemon_client.start_daemon()
    await_for_process_completeness(process)

    widget.join()  # Make sure the thread is finished.

    assert test_variable
    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_nodes_tree_widget(multiply_add_completed_workchain):
    """Test ProcessNodesTreeWidget with a simple `WorkChainNode`"""
    awb.ProcessNodesTreeWidget(value=multiply_add_completed_workchain.uuid)
