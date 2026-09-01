import ipywidgets as ipw
import pytest
from aiida import engine, orm
from aiida.workflows.arithmetic.multiply_add import MultiplyAddWorkChain

import aiidalab_widgets_base as awb


@pytest.mark.usefixtures("aiida_profile_clean")
def test_submit_button_widget(multiply_add_process_builder_ready):
    """Test SubmitButtonWidget with a simple `WorkChainNode`."""

    def hook(_=None):
        pass

    def return_inputs():
        return multiply_add_process_builder_ready

    widget = awb.SubmitButtonWidget(
        process_class=MultiplyAddWorkChain, inputs_generator=return_inputs
    )

    widget.on_submitted(hook)

    assert widget.process is None

    widget.on_btn_submit_press()
    assert widget.process is not None
    assert isinstance(widget.process, orm.WorkChainNode)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_follower_widget(multiply_add_process_builder_ready, daemon_client):
    """Test ProcessFollowerWidget with a simple `WorkChainNode`."""
    widget = awb.ProcessFollowerWidget()

    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    widget = awb.ProcessFollowerWidget(process=process)

    daemon_client.start_daemon()
    widget.follow()
    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_monitor(
    multiply_add_process_builder_ready, daemon_client, await_for_process_completeness
):
    """Test ProcessMonitor with a simple `WorkChainNode`."""
    awb.ProcessMonitor()

    if daemon_client.is_daemon_running:
        daemon_client.stop_daemon(wait=True)
    process = engine.submit(multiply_add_process_builder_ready)

    test_variable = False

    def callback():
        nonlocal test_variable
        test_variable = True

    widget = awb.ProcessMonitor(value=process.uuid, callbacks=[callback])

    daemon_client.start_daemon()
    await_for_process_completeness(process)

    widget.join()

    assert test_variable
    daemon_client.stop_daemon(wait=True)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_nodes_tree_widget(multiply_add_completed_workchain):
    """Test ProcessNodesTreeWidget with a simple `WorkChainNode`."""
    awb.ProcessNodesTreeWidget(value=multiply_add_completed_workchain.uuid)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_monitor_log_widget(multiply_add_completed_workchain):
    """Test that a failing callback's traceback is written to `log_widget`."""

    def failing_callback():
        raise RuntimeError("callback exploded")

    def run_and_join():
        widget = awb.ProcessMonitor(
            value=multiply_add_completed_workchain.uuid,
            callbacks=[failing_callback],
            log_widget=log_widget,
        )
        widget.join()

    log_widget = ipw.VBox()
    with pytest.warns(UserWarning, match="failing_callback"):
        run_and_join()

    assert len(log_widget.children) == 1
    assert isinstance(log_widget.children[0], ipw.HTML)
    assert "callback exploded" in log_widget.children[0].value
