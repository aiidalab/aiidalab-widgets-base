"""The wizard application allows the implication of a Wizard-like GUI.

Authors:

    * Carl Simon Adorf <simon.adorf@epfl.ch>
"""
from enum import Enum
from time import sleep
from time import time
from threading import Thread

import traitlets
import ipywidgets as ipw


class WizardAppWidget(ipw.VBox):
    class State(Enum):
        "Every step within the WizardAppWidget must have this traitlet."
        INIT = 0  # implicit default value

        CONFIGURED = 1
        READY = 2
        ACTIVE = 3
        SUCCESS = 4

        # All error states have negative codes
        FAIL = -1

    ICON_SEPARATOR = "\u2000"  # en-dash  (placed between title and icon)

    ICONS = {
        State.INIT: "\u25cb",
        State.READY: "\u25ce",
        State.CONFIGURED: "\u25cf",
        State.ACTIVE: ["\u25dc", "\u25dd", "\u25de", "\u25df"],
        State.SUCCESS: "\u2713",
        State.FAIL: "\u00d7",
    }

    @classmethod
    def icons(cls):
        """Return the icon set and return animated icons based on the current time stamp."""
        t = time()
        return {
            key: item
            if isinstance(item, str)
            else item[int((t * len(item) % len(item)))]
            for key, item in cls.ICONS.items()
        }

    selected_index = traitlets.Int()

    def __init__(self, steps, **kwargs):
        # The number of steps must be greater than one
        # for this app's logic to make sense.
        assert len(steps) > 1
        self.steps = steps

        # Unzip the steps to titles and widgets.
        self.titles, widgets = zip(*steps)

        # Initialize the accordion with the widgets ...
        self.accordion = ipw.Accordion(children=widgets)
        self._update_titles()
        ipw.link((self.accordion, "selected_index"), (self, "selected_index"))

        # Automatically update titles to implement the "spinner"

        def spinner_thread():
            while True:
                sleep(0.1)
                self._update_titles()

        Thread(target=spinner_thread).start()

        # Watch for changes to each step's state
        for widget in widgets:
            assert widget.has_trait("state")
            widget.observe(self._update_step_state, names=["state"])

        self.reset_button = ipw.Button(
            description="Reset",
            icon="undo",
            layout=ipw.Layout(width="auto", flex="1 1 auto"),
            tooltip="Reset the app to start over (if possible)",
            disabled=True,
        )
        self.reset_button.on_click(self._on_click_reset_button)

        # Create a back-button, to switch to the previous step when possible:
        self.back_button = ipw.Button(
            description="Previous step",
            icon="step-backward",
            layout=ipw.Layout(width="auto", flex="1 1 auto"),
            tooltip="Go to the previous step.",
            disabled=True,
        )
        self.back_button.on_click(self._on_click_back_button)

        # Create a next-button, to switch to the next step when appropriate:
        self.next_button = ipw.Button(
            description="Next step",
            icon="step-forward",
            layout=ipw.Layout(width="auto", flex="1 1 auto"),
            tooltip="Go to the next step.",
            disabled=True,
        )
        self.next_button.on_click(self._on_click_next_button)

        self.footer = ipw.HBox(
            children=[self.back_button, self.reset_button, self.next_button]
        )

        super().__init__(children=[self.footer, self.accordion], **kwargs)

    def _update_titles(self):
        for i, (title, widget) in enumerate(zip(self.titles, self.accordion.children)):
            icon = self.icons().get(widget.state, str(widget.state).upper())
            self.accordion.set_title(i, f"{icon} Step {i+1}: {title}")

    def _consider_switch(self, _=None):
        with self.hold_trait_notifications():
            index = self.accordion.selected_index
            last_step_selected = index + 1 == len(self.accordion.children)
            selected_widget = self.accordion.children[index]
            if (
                selected_widget.auto_next
                and not last_step_selected
                and selected_widget.state == self.State.SUCCESS
            ):
                self.accordion.selected_index += 1

    def _update_step_state(self, _):
        with self.hold_trait_notifications():
            self._update_titles()
            self._update_buttons()
            self._consider_switch()

    @traitlets.observe("selected_index")
    def _observe_selected_index(self, change):
        "Activate/deactivate the next-button based on which step is selected."
        self._update_buttons()

    def can_reset(self):
        steps = [
            self.accordion.children[idx] for idx in range(len(self.accordion.children))
        ]

        if any(not step.can_reset() for step in steps):
            return False

        if any(step.state is not self.State.INIT for step in steps):
            return True

    def _update_buttons(self):
        with self.hold_trait_notifications():
            index = self.accordion.selected_index
            if index is None:
                self.back_button.disabled = True
                self.next_button.disabled = True
                self.reset_button.disabled = True
            else:
                first_step_selected = index == 0
                last_step_selected = index + 1 == len(self.accordion.children)
                selected_widget = self.accordion.children[index]

                self.back_button.disabled = (
                    first_step_selected
                    or selected_widget.state
                    in (self.State.ACTIVE, self.State.SUCCESS, self.State.FAIL)
                )
                self.next_button.disabled = (
                    last_step_selected
                    or selected_widget.state is not self.State.SUCCESS
                )

                self.reset_button.disabled = not self.can_reset()

    def reset(self, step=0):
        """Reset the app down to the given step.

        For example, with step=0 (the default), the whole app is reset.
        With step=1, all but the first step are reset.
        """
        with self.hold_sync():
            for index in range(step, len(self.accordion.children)):
                if hasattr(self.accordion.children[index], "reset"):
                    self.accordion.children[index].reset()

    def _on_click_reset_button(self, _):
        with self.hold_sync():
            self.reset()
            self.accordion.selected_index = 0

    def _on_click_back_button(self, _):
        self.accordion.selected_index -= 1

    def _on_click_next_button(self, _):
        self.accordion.selected_index += 1


class WizardAppWidgetStep(traitlets.HasTraits):
    "One step of a WizardAppWidget."

    state = traitlets.UseEnum(WizardAppWidget.State)
    auto_next = traitlets.Bool()

    def can_reset(self):
        return hasattr(self, "reset")
