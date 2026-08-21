import base64
import json
import zlib

import ipywidgets as ipw

from aiidalab_widgets_base import bug_report


def test_fingerprint_parser():
    """Test get_environment_fingerprint function and parse it out."""

    encoding = "utf-8"
    fingerprint = bug_report.get_environment_fingerprint(encoding)

    # Parse the fingerprint.
    data = bug_report.parse_environment_fingerprint(fingerprint)

    # To test, manually generate the fingerprint and compare it to the output of the parser.
    json_data = json.dumps(data, separators=(",", ":"))
    got = base64.urlsafe_b64encode(zlib.compress(json_data.encode(encoding), level=9))

    assert got == fingerprint


def test_install_create_github_issue_exception_handler(monkeypatch):
    """Test that the installed exception handler renders a bug-report link into `output`."""

    class FakeIPython:
        _showtraceback = "original-handler"

    fake_ipython = FakeIPython()
    monkeypatch.setattr(bug_report, "_ORIGINAL_EXCEPTION_HANDLER", None)
    monkeypatch.setattr("IPython.get_ipython", lambda: fake_ipython)

    output = ipw.VBox()
    restore = bug_report.install_create_github_issue_exception_handler(
        output,
        url="https://github.com/aiidalab/aiidalab-qe/issues/new",
        labels=("bug", "automated-report"),
    )

    # Installing the handler replaces IPython's traceback display with a
    # callable closure, not just some other placeholder value.
    assert callable(fake_ipython._showtraceback)
    assert fake_ipython._showtraceback != "original-handler"

    traceback_lines = [
        "Traceback (most recent call last):\n",
        "ValueError: boom\n",
    ]
    fake_ipython._showtraceback(ValueError, ValueError("boom"), traceback_lines)

    assert len(output.children) == 1
    msg = output.children[0]
    assert isinstance(msg, ipw.HTML)
    assert "aiidalab-qe/issues/new" in msg.value
    assert "boom" in msg.value

    # Restoring puts the original handler back.
    restore()
    assert fake_ipython._showtraceback == "original-handler"
