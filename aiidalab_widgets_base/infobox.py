from __future__ import annotations

import ipywidgets as ipw


class InfoBox(ipw.VBox):
    """The `InfoBox` component is used to provide additional info regarding a widget or an app."""

    def __init__(self, classes: list[str] | None = None, **kwargs):
        """`InfoBox` constructor.

        Parameters
        ----------
        `classes` : `list[str]`, optional
            One or more CSS classes.
        """
        super().__init__(**kwargs)
        self.add_class("info-box")
        for custom_classes in classes or []:
            for custom_class in custom_classes.split(" "):
                if custom_class:
                    self.add_class(custom_class)


class InAppGuide(InfoBox):
    """The `InfoAppGuide` is used to set up in-app guides that may be toggle in unison."""

    def __init__(self, guide_id: str, classes: list[str] | None = None, **kwargs):
        """`InAppGuide` constructor.

        Parameters
        ----------
        `guide_id` : `str`
            The unique identifier for the guide.
        `classes` : `list[str]`, optional
            One or more CSS classes.
        """
        classes = ["in-app-guide", *(classes or []), guide_id]
        super().__init__(classes=classes, **kwargs)


class FirstTimeUserMessage(ipw.VBox):
    """The `FirstTimeUserMessage` is used to display a message to first time users."""

    def __init__(self, message="", **kwargs):
        """`FirstTimeUserMessage` constructor."""

        self.close_button = ipw.Button(
            icon="times",
            tooltip="Close",
        )

        self.message_box = InfoBox(
            children=[
                ipw.HTML(message),
                self.close_button,
            ],
        )

        self.undo_button = ipw.Button(
            icon="undo",
            tooltip="Undo",
            description="undo",
        )

        self.closing_message = ipw.HBox(
            children=[
                ipw.HTML("This message will not show next time"),
                self.undo_button,
            ],
        )
        self.closing_message.add_class("closing-message")

        super().__init__(
            children=[
                self.closing_message,
                self.message_box,
            ],
            **kwargs,
        )

        self.add_class("first-time-users-infobox")

        self._check_if_first_time_user()

        self._set_event_listeners()

    def _check_if_first_time_user(self):
        """Add a message for first-time users."""
        try:
            with open(".app-user-config") as file:
                first_time_user = file.read().find("existing-user") == -1
        except FileNotFoundError:
            first_time_user = True

        if first_time_user:
            self.layout.display = "flex"
            self.message_box.layout.display = "flex"
            self.closing_message.layout.display = "none"

    def _on_close(self, _=None):
        """Hide the first time info box and write existing user token to file."""
        self.message_box.layout.display = "none"
        self.closing_message.layout.display = "flex"
        self._write_existing_user_token_to_file()

    def _write_existing_user_token_to_file(self):
        """Write a token to file marking the user as an existing user."""
        with open(".app-user-config", "w") as file:
            file.write("existing-user")

    def _on_undo(self, _=None):
        """Undo the action of closing the first time user message."""
        from contextlib import suppress
        from pathlib import Path

        self.message_box.layout.display = "flex"
        self.closing_message.layout.display = "none"

        with suppress(FileNotFoundError):
            Path(".app-user-config").unlink()

    def _set_event_listeners(self):
        """Set the event listeners."""
        self.close_button.on_click(self._on_close)
        self.undo_button.on_click(self._on_undo)
