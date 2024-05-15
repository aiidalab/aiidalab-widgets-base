"""Provide more user friendly error messages and automated reporting.

Authors:

    * Carl Simon Adorf <simon.adorf@epfl.ch>
"""

from __future__ import annotations

import base64
import json
import platform
import re
import sys
import zlib
from subprocess import run
from textwrap import wrap
from urllib.parse import urlencode, urlsplit, urlunsplit

import ipywidgets as ipw
from ansi2html import Ansi2HTMLConverter


def find_installed_packages(python_bin: str | None = None) -> dict[str, str]:
    """Return all currently installed packages."""
    if python_bin is None:
        python_bin = sys.executable
    output = run(
        [python_bin, "-m", "pip", "list", "--format=json"],
        encoding="utf-8",
        capture_output=True,
        check=True,
    ).stdout

    return {package["name"]: package["version"] for package in json.loads(output)}


def get_environment_fingerprint(encoding="utf-8"):
    data = {
        "version": 1,
        "platform": {
            "architecture": platform.architecture(),
            "python_version": platform.python_version(),
            "version": platform.version(),
        },
        "packages": find_installed_packages(),
    }
    json_data = json.dumps(data, separators=(",", ":"))
    return base64.urlsafe_b64encode(zlib.compress(json_data.encode(encoding), level=9))


def parse_environment_fingerprint(fingerprint, encoding="utf-8"):
    """decode the environment fingerprint and return the data as a dictionary."""
    data = json.loads(
        zlib.decompress(base64.urlsafe_b64decode(fingerprint)).decode(encoding)
    )
    return data


ERROR_MESSAGE = """<div class="alert alert-danger">
<p><strong>
    <i class="fa fa-bug" aria-hidden="true"></i> Oh no... the application crashed due to an unexpected error.
</strong></p>
<a href="{issue_url}" target="_blank" class="btn btn-primary">
    <i class="fa fa-share" aria-hidden="true"></i> Create bug report
</a>
<button
    onclick="Jupyter.notebook.clear_all_output(); Jupyter.notebook.restart_run_all({{confirm: false}})"
    type="button"
    class="btn btn-success">
        <i class="fa fa-refresh" aria-hidden="true"></i> Restart app
</button>
<div style="padding-top: 1em">
    <details style="border: 1px solid #aaa; border-radius: 4px; padding: .5em .5em 0; ">
        <summary style="font-weight: bold; margin: -.5em -.5em 0; padding: .5em">
            <i class="fa fa-code" aria-hidden="true"></i> View the full traceback
        </summary>
      <pre style="color: #333; background: #f8f8f8;"><code>{traceback}</code></pre>
    </details>
</div></div>"""


BUG_REPORT_TITLE = """Bug report: Application crashed with {exception_type}"""

BUG_REPORT_BODY = """## Automated report

_This issue was created with the app's automated bug reporting feature.
Attached to this issue is the full traceback as well as an environment
fingerprint that contains information about the operating system as well as all
installed libraries._

## Additional comments (optional):

_Example: I submitted a band structure calculation for Silica._

## Attachments

<details>
<summary>Traceback</summary>

```python-traceback
{traceback}
```
</details>

<details>
<summary>Environment fingerprint</summary>
<pre>{environment_fingerprint}</pre>
</details>

**By submitting this issue I confirm that I am aware that this information can
potentially be used to determine what kind of calculation was performed at the
time of error.**
"""


def _strip_ansi_codes(msg):
    """Remove any ANSI codes (e.g. color codes)."""
    return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", msg)


def _convert_ansi_codes_to_html(msg):
    """Convert any ANSI codes (e.g. color codes) into HTML."""
    converter = Ansi2HTMLConverter()
    return converter.produce_headers().strip() + converter.convert(msg, full=False)


def _format_truncated_traceback(traceback, max_num_chars=2000):
    """Truncate the traceback to the given character length."""
    n = 0
    for _i, line in enumerate(reversed(traceback)):
        n += len(_strip_ansi_codes(line)) + 2  # add 2 for newline control characters
        if n > max_num_chars:
            break
    return _strip_ansi_codes("\n".join(traceback[-_i:]))


_ORIGINAL_EXCEPTION_HANDLER = None


def install_create_github_issue_exception_handler(output, url, labels=None):
    """Install a GitHub bug report exception handler.

    After installing this handler, kernel exception will show a generic error
    message to the user, with the option to file an automatic bug report at the
    given URL.

    This is an example of how to use this function:

    Example:
    --------
    .. highlight:: python
    .. code-block:: python

        output = ipw.Output()
        install_create_github_issue_exception_handler(
            output,
            url='https://github.com/aiidalab/aiidalab-qe/issues/new',
            labels=('bug', 'automated-report'))

        with output:
            display(welcome_message, app_with_work_chain_selector, footer)

    """
    global _ORIGINAL_EXCEPTION_HANDLER  # noqa

    if labels is None:
        labels = []

    ipython = get_ipython()  # noqa
    _ORIGINAL_EXCEPTION_HANDLER = _ORIGINAL_EXCEPTION_HANDLER or ipython._showtraceback

    def create_github_issue_exception_handler(exception_type, exception, traceback):
        try:
            output.clear_output()

            bug_report_query = {
                "title": BUG_REPORT_TITLE.format(
                    exception_type=str(exception_type.__name__)
                ),
                "body": BUG_REPORT_BODY.format(
                    # Truncate the traceback to a maximum of 2000 characters
                    # and strip all ansi control characters:
                    traceback=_format_truncated_traceback(traceback, 2000),
                    # Determine and format the environment fingerprint to be
                    # included with the bug report:
                    environment_fingerprint="\n".join(
                        wrap(get_environment_fingerprint().decode("utf-8"), 100)
                    ),
                ),
                "labels": ",".join(labels),
            }
            issue_url = urlunsplit(
                urlsplit(url)._replace(query=urlencode(bug_report_query))
            )

            with output:
                msg = ipw.HTML(
                    ERROR_MESSAGE.format(
                        issue_url=issue_url,
                        traceback=_convert_ansi_codes_to_html("\n".join(traceback)),
                        len_url=len(issue_url),
                    )
                )
                display(msg)  # noqa
        except Exception as error:
            print(f"Error while generating bug report: {error}", file=sys.stderr)
            _ORIGINAL_EXCEPTION_HANDLER(exception_type, exception, traceback)

    def restore_original_exception_handler():
        ipython._showtraceback = _ORIGINAL_EXCEPTION_HANDLER

    ipython._showtraceback = create_github_issue_exception_handler

    return restore_original_exception_handler
