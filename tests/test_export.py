import pytest

from aiidalab_widgets_base import export


@pytest.mark.usefixtures("aiida_profile_clean")
def test_export_button_widget(multiply_add_completed_workchain, monkeypatch, tmp_path):
    """Test the export button widget."""

    process = multiply_add_completed_workchain
    button = export.ExportButtonWidget(process)
    assert button.description == f"Export workflow ({process.pk})"

    # Test the export button. monkeypatch the `mkdtemp` function to return a
    # temporary directory in the `tmp_path` fixture to store the export file.
    monkeypatch.setattr("tempfile.mkdtemp", lambda: str(tmp_path))
    button.export_aiida_subgraph()

    assert (tmp_path / "export.aiida").exists()
