from aiida import orm


def test_process_inputs(generate_calc_job_node):
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

    # test the widget can be instantiated with empty inputs
    process_input_widget = ProcessInputsWidget(process=None)

    process_input_widget = ProcessInputsWidget(process=process)
    input_dropdown = process_input_widget._inputs

    assert "parameters" in [key for key, _ in input_dropdown.options]
    assert "nested.inner" in [key for key, _ in input_dropdown.options]

    # select the nested input from dropdown and check that the value is displayed)
    uuid = dict(input_dropdown.options)["nested.inner"]
    input_dropdown.value = uuid

    selected_input = orm.load_node(uuid)

    assert process_input_widget.info.value == f"PK: {selected_input.pk}"
