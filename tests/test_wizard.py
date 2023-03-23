import ipywidgets as ipw
import traitlets as tl


def test_wizard_app_widget():
    from aiidalab_widgets_base import WizardAppWidget, WizardAppWidgetStep

    class Step1(ipw.HBox, WizardAppWidgetStep):
        config = tl.Bool()

        def __init__(self, **kwargs):
            self.order_button = ipw.Button(description="Submit order", disabled=False)
            self.order_button.on_click(self.submit_order)
            super().__init__(children=[self.order_button], **kwargs)

        def submit_order(self, _=None):
            self.state = self.State.SUCCESS
            self.config = True

        @tl.default("config")
        def _default_config(self):
            return False

        def reset(self):
            self.config = False
            self.state = self.State.INIT

    class Step2(ipw.HBox, WizardAppWidgetStep):
        config = tl.Bool()

        def __init__(self, **kwargs):
            self.results = ipw.HTML("Results")
            super().__init__(children=[self.results], **kwargs)

        def submit_order(self, _=None):
            pass

        @tl.default("config")
        def _default_config(self):
            return False

        @tl.observe("config")
        def _observe_config(self, change):
            if self.config:
                self.state = self.State.READY
            else:
                self.state = self.State.INIT

    s1 = Step1(auto_advance=True)
    s2 = Step2(auto_advance=True)
    tl.dlink((s1, "config"), (s2, "config"))

    widget = WizardAppWidget(
        steps=[
            ("Setup", s1),
            ("View results", s2),
        ],
        testing=True,
    )

    # Check initial state.
    assert s1.state == s1.State.INIT
    assert s2.state == s2.State.INIT
    assert widget.accordion.selected_index == 0

    s1.order_button.click()

    # Check state after finishing the first step.
    assert s1.state == s1.State.SUCCESS
    assert s2.state == s2.State.READY
    assert widget.accordion.selected_index == 1
    assert widget.next_button.disabled is True

    # Check state after resetting the app.
    widget.reset()
    assert s1.state == s1.State.INIT
    assert s2.state == s2.State.INIT
    assert widget.back_button.disabled is True
