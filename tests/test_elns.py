from aiidalab_eln import CheminfoElnConnector

from aiidalab_widgets_base import elns


def test_connect_to_eln(mock_eln_config):
    """Test the connect_to_eln function."""
    mock_eln_config.mock(original_config=elns.ELN_CONFIG)

    eln, message = elns.connect_to_eln(eln_instance="any_random_eln")
    assert eln is None
    assert message.startswith("Can't open")

    # Now, create a config file with {} content
    mock_eln_config.write(config_dictionary={})

    # Now check that empty config file is identified, but has no content.
    eln, message = elns.connect_to_eln()
    assert eln is None
    assert message.startswith(
        "No ELN instance was provided, the default ELN instance is not configured either."
    )
    eln, message = elns.connect_to_eln(eln_instance="any_random_eln")
    assert eln is None
    assert message == "Didn't find configuration for the 'any_random_eln' instance."

    # Populate the config file with some content.
    mock_eln_config.populate_mock_config_with_cheminfo()

    # Now check that the config file is identified and has content.
    eln, message = elns.connect_to_eln()
    assert isinstance(eln, CheminfoElnConnector)

    mock_eln_config.restore()


def test_eln_import_widget():
    """Test the ElnImportWidget."""

    # At the moment, we do a very minimal test of the widget, because it requires a running ELN instance.
    # TODO: add a mock ELN instance.

    widget = elns.ElnImportWidget()
    assert widget.node is None


def test_eln_export_widget(structure_data_object, mock_eln_config):
    """Test the ElnExportWidget."""

    # At the moment, we do a very minimal test of the widget, because it requires a running ELN instance.
    # TODO: add a mock ELN instance.

    mock_eln_config.mock(original_config=elns.ELN_CONFIG)

    mock_eln_config.populate_mock_config_with_cheminfo()

    widget = elns.ElnExportWidget()
    assert widget.node is None

    widget.node = structure_data_object
    assert widget.eln.sample_uuid_widget.value == "12345abcde"
    assert widget.eln.file_name_widget.value == "file.xyz"

    mock_eln_config.restore()


def test_eln_configure_widget(mock_eln_config):
    mock_eln_config.mock(original_config=elns.ELN_CONFIG)

    widget = elns.ElnConfigureWidget()
    assert widget.eln_instance.options == (("Setup new ELN", {}),)

    widget.eln_types.value = "cheminfo"
    widget.eln.eln_instance = "https://mydb.cheminfo.org/"
    widget.eln.token = "1234567890abcdef"

    widget.save_eln_configuration()

    assert widget.eln_instance.options == (
        ("Setup new ELN", {}),
        (
            "https://mydb.cheminfo.org/",
            {"eln_type": "cheminfo", "token": "1234567890abcdef"},
        ),
    )

    assert "https://mydb.cheminfo.org/" in mock_eln_config.get()
    assert (
        mock_eln_config.get()["https://mydb.cheminfo.org/"]["token"]
        == "1234567890abcdef"
    )
    assert "default" not in mock_eln_config.get()

    widget.eln_instance.label = "https://mydb.cheminfo.org/"
    widget.set_current_eln_as_default()
    assert "default" in mock_eln_config.get()

    # Update the configuration and check that it is updated.
    widget.eln.token = "new-1234567890abcdef"
    widget.save_eln_configuration()
    assert (
        mock_eln_config.get()["https://mydb.cheminfo.org/"]["token"]
        == "new-1234567890abcdef"
    )

    widget.erase_current_eln_from_configuration()

    assert "https://mydb.cheminfo.org/" not in mock_eln_config.get()

    mock_eln_config.restore()
