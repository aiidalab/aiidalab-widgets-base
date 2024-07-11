from pathlib import Path

from aiidalab_widgets_base.infobox import FirstTimeUserMessage, InAppGuide, InfoBox


def test_infobox_classes():
    """Test `InfoBox` classes."""
    infobox = InfoBox()
    assert "info-box" in infobox._dom_classes
    infobox = InfoBox(**{"custom-css": "custom-info-box"})
    assert all(
        css_class in infobox._dom_classes
        for css_class in (
            "info-box",
            "custom-info-box",
        )
    )


def test_in_app_guide():
    """Test `InAppGuide` class."""
    guide_class = "some_guide"
    in_app_guide = InAppGuide(guide_class=guide_class)
    assert all(
        css_class in in_app_guide._dom_classes
        for css_class in (
            "info-box",
            "in-app-guide",
            guide_class,
        )
    )


def test_first_time_user_message():
    """Test `FirstTimeUserMessage` class."""
    message = "Hello, first-time user!"
    widget = FirstTimeUserMessage(message=message)
    assert "first-time-users-infobox" in widget._dom_classes
    assert widget.message_box.children[0].value == message  # type: ignore
    assert widget.layout.display == "flex"
    assert widget.message_box.layout.display == "flex"
    assert widget.closing_message.layout.display == "none"
    widget.close_button.click()
    assert widget.message_box.layout.display == "none"
    assert widget.closing_message.layout.display == "flex"
    path = Path(".app-user-config")
    assert path.exists()
    assert path.read_text().find("existing-user") != -1
    widget.undo_button.click()
    assert widget.message_box.layout.display == "flex"
    assert widget.closing_message.layout.display == "none"
    assert not path.exists()
