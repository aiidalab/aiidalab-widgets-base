from pathlib import Path

from aiidalab_widgets_base.infobox import FirstTimeUserMessage, InAppGuide, InfoBox


def test_infobox_classes():
    """Test `InfoBox` classes."""
    custom_classes = ["custom-1", "custom-2 custom-3"]
    infobox = InfoBox(classes=custom_classes)
    assert all(
        css_class in infobox._dom_classes
        for css_class in (
            "info-box",
            "custom-1",
            "custom-2",
            "custom-3",
        )
    )


def test_in_app_guide():
    """Test `InAppGuide` class."""
    guide_id = "some_guide"
    in_app_guide = InAppGuide(guide_id=guide_id)
    assert all(
        css_class in in_app_guide._dom_classes
        for css_class in (
            "info-box",
            "in-app-guide",
            guide_id,
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
