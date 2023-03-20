import pytest
from aiida import engine, orm


@pytest.mark.usefixtures("aiida_profile_clean")
def test_submit_button_widget(multiply_add_process_builder_ready):
    """Test SubmitButtonWidget with a simple `WorkChainNode`"""
    from aiida.workflows.arithmetic.multiply_add import MultiplyAddWorkChain

    import aiidalab_widgets_base as awb

    def hook(_=None):
        pass

    def return_inputs():
        return multiply_add_process_builder_ready

    widget = awb.SubmitButtonWidget(
        process_class=MultiplyAddWorkChain, inputs_generator=return_inputs
    )

    widget.on_submitted(hook)

    # Simulate the click on the button.
    widget.on_btn_submit_press()


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_inputs_widget(generate_calc_job_node):
    """Test ProcessInputWidget with a simple `CalcJobNode`"""
    from aiidalab_widgets_base.process import ProcessInputsWidget

    process = generate_calc_job_node(
        inputs={
            "parameters": orm.Int(1),
            "nested": {
                "inner": orm.Int(2),
            },
        }
    )

    # Test the widget can be instantiated with empty inputs
    process_input_widget = ProcessInputsWidget()

    process_input_widget = ProcessInputsWidget(process=process)
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
    from aiidalab_widgets_base.process import ProcessOutputsWidget

    # Test the widget can be instantiated with empty inputs
    widget = ProcessOutputsWidget()

    # Test the widget can be instantiated with a process
    widget = ProcessOutputsWidget(process=multiply_add_completed_workchain)

    # Simulate output selection.
    widget.show_selected_output(change={"new": "result"})


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_follower_widget(multiply_add_process_builder_ready):
    """Test ProcessFollowerWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base.process import ProcessFollowerWidget

    # Test the widget can be instantiated with empty inputs
    widget = ProcessFollowerWidget()

    process = engine.submit(multiply_add_process_builder_ready)

    process.seal()

    # Test the widget can be instantiated with a process
    widget = ProcessFollowerWidget(process=process)

    # Follow the process till it is completed.
    widget.follow()


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_report_widget(multiply_add_completed_workchain):
    """Test ProcessReportWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base.process import ProcessReportWidget

    # Test the widget can be instantiated with empty inputs
    ProcessReportWidget()

    # Test the widget can be instantiated with a process
    ProcessReportWidget(process=multiply_add_completed_workchain)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_call_stack_widget(multiply_add_completed_workchain):
    """Test ProcessCallStackWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base.process import ProcessCallStackWidget

    # Test the widget can be instantiated with empty inputs
    ProcessCallStackWidget()

    # Test the widget can be instantiated with a process
    ProcessCallStackWidget(process=multiply_add_completed_workchain)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_progress_bar_widget(multiply_add_completed_workchain):
    """Test ProgressBarWidget with a simple `WorkChainNode`"""
    from aiidalab_widgets_base import ProgressBarWidget

    # Test the widget can be instantiated with empty inputs
    ProgressBarWidget()

    # Test the widget can be instantiated with a process
    ProgressBarWidget(process=multiply_add_completed_workchain)


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

    # Test the widget can be instantiated with a process
    RunningCalcJobOutputWidget(calculation=process)


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_list_widget(multiply_add_completed_workchain):
    """Test ProcessListWidget with a simple `WorkChainNode`"""

    from aiidalab_widgets_base.process import ProcessListWidget

    ProcessListWidget()


@pytest.mark.usefixtures("aiida_profile_clean")
def test_process_nodes_tree_widget(multiply_add_completed_workchain):
    """Test ProcessNodesTreeWidget with a simple `WorkChainNode`"""

    from aiidalab_widgets_base.process import ProcessNodesTreeWidget

    ProcessNodesTreeWidget(value=multiply_add_completed_workchain.uuid)
