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
        _showtraceback = lambda self, _exc_type, _exc, _traceback: "original-handler"

    fake_ipython = FakeIPython()
    monkeypatch.setattr(bug_report, "_ORIGINAL_EXCEPTION_HANDLER", None)
    monkeypatch.setattr("IPython.get_ipython", lambda: fake_ipython)

    assert (
        fake_ipython._showtraceback(ValueError, ValueError("boom"), [])
        == "original-handler"
    )

    output = ipw.VBox()
    restore = bug_report.install_create_github_issue_exception_handler(
        output,
        url="https://github.com/aiidalab/aiidalab-qe/issues/new",
        labels=("bug", "automated-report"),
    )

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
    assert (
        fake_ipython._showtraceback(ValueError, ValueError("boom"), [])
        == "original-handler"
    )


def test_install_create_github_issue_exception_handler_fallback_on_error(monkeypatch):
    """Test that a failure while building the report clears stale content and
    falls back to the original handler, instead of leaving a previous crash's
    bug-report panel on screen."""

    calls = []

    class FakeIPython:
        def _showtraceback(self, *args):
            calls.append(args)

    fake_ipython = FakeIPython()
    monkeypatch.setattr(bug_report, "_ORIGINAL_EXCEPTION_HANDLER", None)
    monkeypatch.setattr("IPython.get_ipython", lambda: fake_ipython)

    # Simulate a bug-report panel already on screen from a previous crash.
    output = ipw.VBox(children=[ipw.HTML("stale content from a previous crash")])
    bug_report.install_create_github_issue_exception_handler(
        output, url="https://github.com/aiidalab/aiidalab-qe/issues/new"
    )

    def _raise_fingerprint_error(*args, **kwargs):
        raise RuntimeError("pip listing failed")

    # Force a failure between `output.children = ()` and `output.children = (msg,)`.
    monkeypatch.setattr(
        bug_report, "get_environment_fingerprint", _raise_fingerprint_error
    )

    fake_ipython._showtraceback(ValueError, ValueError("boom"), ["boom\n"])

    # The stale panel was cleared, not left in place.
    assert len(output.children) == 0
    # The failure fell back to the original handler with the original exception info.
    assert len(calls) == 1
    assert calls[0][0] is ValueError
