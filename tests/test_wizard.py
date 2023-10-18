import ipywidgets as ipw
import traitlets as tl

from aiidalab_widgets_base import WizardAppWidget, WizardAppWidgetStep


def test_wizard_app_widget():
    class Step1(ipw.HBox, WizardAppWidgetStep):
        config = tl.Bool()

        def __init__(self, **kwargs):
            self.order_button = ipw.Button(description="Submit order", disabled=False)
            self.order_button.on_click(self.submit_order)
            super().__init__(children=[self.order_button], **kwargs)

        def submit_order(self, _=None):
            self.config = True

        @tl.default("config")
        def _default_config(self):
            return False

        def reset(self):
            self.config = False

        @tl.observe("config")
        def _observe_config(self, _=None):
            self.state = self.State.SUCCESS if self.config else self.State.INIT

    class Step2(ipw.HBox, WizardAppWidgetStep):
        config = tl.Bool()

        def __init__(self, **kwargs):
            self.results = ipw.HTML("Results")
            super().__init__(children=[self.results], **kwargs)

        def submit_order(self, _=None):
            pass

        def reset(self):
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
    )

    # Check initial state.
    assert s1.state == s1.State.INIT
    assert s2.state == s2.State.INIT
    assert widget.accordion.selected_index == 0
    assert widget.next_button.disabled is True
    assert widget.back_button.disabled is True
    assert widget.accordion.get_title(0) == "○ Step 1: Setup"
    assert widget.accordion.get_title(1) == "○ Step 2: View results"
    assert not widget.can_reset()

    # Check state after finishing the first step.
    s1.order_button.click()
    assert s1.state == s1.State.SUCCESS
    assert s2.state == s2.State.READY
    assert widget.accordion.selected_index == 1
    assert widget.next_button.disabled is True
    assert widget.back_button.disabled is False
    assert widget.accordion.get_title(0) == "✓ Step 1: Setup"
    assert widget.accordion.get_title(1) == "◎ Step 2: View results"
    assert widget.can_reset()

    # Check state after resetting the app.
    widget.reset_button.click()
    assert s1.state == s1.State.INIT
    assert s2.state == s2.State.INIT
    assert widget.back_button.disabled is True
    assert widget.next_button.disabled is True
    assert widget.accordion.get_title(0) == "○ Step 1: Setup"
    assert widget.accordion.get_title(1) == "○ Step 2: View results"
    assert not widget.can_reset()

    # Check state after finishing the first step again.
    s1.config = True  # This should trigger an attempt to advance to the next step.
    assert s1.state == s1.State.SUCCESS
    assert s2.state == s2.State.READY
    assert widget.accordion.selected_index == 1
    assert widget.next_button.disabled is True
    assert widget.back_button.disabled is False
    assert widget.accordion.get_title(0) == "✓ Step 1: Setup"
    assert widget.accordion.get_title(1) == "◎ Step 2: View results"
    assert widget.can_reset()

    # Click on the back button.
    widget.back_button.click()
    assert s1.state == s1.State.SUCCESS
    assert s2.state == s2.State.READY
    assert widget.accordion.selected_index == 0
    assert widget.next_button.disabled is False
    assert widget.back_button.disabled is True
    assert widget.can_reset()

    # Click on the next button.
    widget.next_button.click()
    assert widget.accordion.selected_index == 1
    assert widget.next_button.disabled is True
    assert widget.back_button.disabled is False
