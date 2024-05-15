"""The wizard application allows the implication of a Wizard-like GUI.

Authors:

    * Carl Simon Adorf <simon.adorf@epfl.ch>
"""

import enum

import ipywidgets as ipw
import traitlets as tl


class AtLeastTwoStepsWizardError(ValueError):
    """Using WizardAppWidget only makes sense if the number of setps is at least two."""

    def __init__(self, steps):
        super().__init__(
            f"The number of steps of a WizardAppWidget must be at least two, but {len(steps)} were provided."
        )


class WizardAppWidgetStep(tl.HasTraits):
    "One step of a WizardAppWidget."

    class State(enum.Enum):
        """Each step is always in one specific state.

        The state is used to determine:

            1) how the step is visually presented to the user, and
            2) whether the next step is accessible (i.e. reached the SUCCESS state).

        App developers are encouraged to use the step states to couple application
        logic and interface. In general, all widget changes should trigger
        a re-evaluation of the step state, and states also determine whether certain
        widgets are enabled or disabled.

        A step can be in one of the following states:

            INIT: The initial state, usually all widgets disabled.
            READY: The step (widget) is ready for user input (some or all widgets enabled).
            CONFIGURED: The step is in a consistent configuration awaiting confirmation.
            ACTIVE: The step is carrying out a runtime operation.
            SUCCESS: A configuration has been confirmed / a runtime operation successfully finished.
            FAIL: A runtime operation has failed in an unrecoverable way.

        Not all steps must implement all states, for example:

            - the first step does not need an INIT state
            - a step without runtime process should not have an ACTIVE or FAIL state
            - a "review & confirm" step does not require a READY state.
            - a step without configuration options (e.g. pure "review & confirm" step)

        Important: The next step is only accessible if the current step is within the SUCCESS
        state!
        """

        INIT = 0  # the step is initialized and all widgets are typically disabled

        # The step is correctly configured and can in principle be confirmed.
        CONFIGURED = 1  # configuration is valid
        READY = 2  # step is ready for user input
        ACTIVE = 3  # step is carrying out a runtime operation
        SUCCESS = 4  # step has successfully completed

        # All error states have negative codes
        FAIL = -1  # the step has unrecoverably failed

    state = tl.UseEnum(State)
    auto_advance = tl.Bool()

    def can_reset(self):
        return hasattr(self, "reset")


class WizardAppWidget(ipw.VBox):
    ICON_SEPARATOR = "\u2000"  # en-dash  (placed between title and icon)

    ICONS = {
        WizardAppWidgetStep.State.INIT: "\u25cb",
        WizardAppWidgetStep.State.READY: "\u25ce",
        WizardAppWidgetStep.State.CONFIGURED: "\u25cf",
        WizardAppWidgetStep.State.ACTIVE: "\u231b",
        WizardAppWidgetStep.State.SUCCESS: "\u2713",
        WizardAppWidgetStep.State.FAIL: "\u00d7",
    }

    selected_index = tl.Int(allow_none=True)

    def __init__(self, steps, **kwargs):
        # The number of steps must be greater than one
        # for this app's logic to make sense.
        if len(steps) < 2:
            raise AtLeastTwoStepsWizardError(steps)

        self.steps = steps

        # Unzip the steps to titles and widgets.
        self.titles, widgets = zip(*steps)

        # Initialize the accordion with the widgets ...
        self.accordion = ipw.Accordion(children=widgets)
        self._update_titles()
        ipw.link((self.accordion, "selected_index"), (self, "selected_index"))

        # Watch for changes to each step's state
        for widget in widgets:
            if not widget.has_trait("state"):
                raise TypeError(
                    f"The provided {widget!r} as wizard app step has no `state` trait. "
                    "It is expected that step classes are derived from the WizardAppWidgetStep class."
                )
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

        header = ipw.HBox(
            children=[self.back_button, self.reset_button, self.next_button]
        )

        super().__init__(children=[header, self.accordion], **kwargs)

    def _update_titles(self):
        for i, (title, widget) in enumerate(zip(self.titles, self.accordion.children)):
            icon = self.ICONS.get(widget.state, str(widget.state).upper())
            self.accordion.set_title(i, f"{icon} Step {i+1}: {title}")

    def _consider_auto_advance(self, _=None):
        """Determine whether the app should automatically advance to the next step.

        This is performed whenever the current step is within the SUCCESS state and has
        the auto_advance attribute set to True.
        """
        if self.accordion.selected_index is None:  # All children are hidden
            return

        with self.hold_trait_notifications():
            index = self.accordion.selected_index
            last_step_selected = index + 1 == len(self.accordion.children)
            selected_widget = self.accordion.children[index]
            if (
                selected_widget.auto_advance
                and not last_step_selected
                and selected_widget.state == WizardAppWidgetStep.State.SUCCESS
            ):
                self.accordion.selected_index += 1

    def _update_step_state(self, _):
        with self.hold_trait_notifications():
            self._update_titles()
            self._update_buttons()
            self._consider_auto_advance()

    @tl.observe("selected_index")
    def _observe_selected_index(self, change):
        "Activate/deactivate the next-button based on which step is selected."
        self._update_buttons()

    def can_reset(self):
        steps = [
            self.accordion.children[idx] for idx in range(len(self.accordion.children))
        ]

        if not all(step.can_reset() for step in steps):
            return False

        if any(step.state is not WizardAppWidgetStep.State.INIT for step in steps):
            return True

        return False

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
                    in (
                        WizardAppWidgetStep.State.ACTIVE,
                        WizardAppWidgetStep.State.SUCCESS,
                        WizardAppWidgetStep.State.FAIL,
                    )
                )
                self.next_button.disabled = (
                    last_step_selected
                    or selected_widget.state is not WizardAppWidgetStep.State.SUCCESS
                )

                self.reset_button.disabled = not self.can_reset()

    def reset(self, step=0):
        """Reset the app up to the given step.

        For example, with step=0 (the default), the whole app is reset.
        With step=1, all but the first step are reset.
        """
        with self.hold_sync():
            for index in reversed(range(step, len(self.accordion.children))):
                if hasattr(self.accordion.children[index], "reset"):
                    self.accordion.children[index].reset()
            self.accordion.selected_index = step

    def _on_click_reset_button(self, _):
        self.reset()

    def _on_click_back_button(self, _):
        self.accordion.selected_index -= 1

    def _on_click_next_button(self, _):
        self.accordion.selected_index += 1
