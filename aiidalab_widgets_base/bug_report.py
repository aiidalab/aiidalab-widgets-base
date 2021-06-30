"""Provide more user friendly error messages and automated reporting.

Authors:

    * Carl Simon Adorf <simon.adorf@epfl.ch>
"""
import base64
import json
import platform
import re
import sys
import zlib
from textwrap import wrap
from urllib.parse import (
    urlencode,
    urlsplit,
    urlunsplit,
)

import ipywidgets as ipw

from aiidalab.utils import find_installed_packages


def get_environment_fingerprint(encoding="utf-8"):
    packages = find_installed_packages()
    data = {
        "version": 1,
        "platform": {
            "architecture": platform.architecture(),
            "python_version": platform.python_version(),
            "version": platform.version(),
        },
        "packages": {package.name: package.version for package in packages},
    }
    json_data = json.dumps(data, separators=(",", ":"))
    return base64.urlsafe_b64encode(zlib.compress(json_data.encode(encoding), level=9))


def parse_environment_fingerprint(data, encoding="utf-8"):
    packages = json.loads(
        zlib.decompress(base64.urlsafe_b64decode(data)).decode(encoding)
    )
    return packages


ERROR_MESSAGE = """<div class="alert alert-danger">
<p><strong><i class="fa fa-bug" aria-hidden="true"></i> Oh no... the application crashed due to an unexpected error.</strong></p>
<p>Please click <a href="{issue_url}" target="_blank">here</a> to submit an automatically created bug report.</p>
<details>
  <summary><u>View the full traceback</u></summary>
  <pre>{traceback}</pre>
</details>
</div>"""


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


_ORIGINAL_EXCEPTION_HANDLER = None


def install_create_github_issue_exception_handler(output, url, labels=None):
    """Install a GitHub bug report exception handler.

    After installing this handler, kernel exception will show a generic error
    message to the user, with the option to file an automatic bug report at the
    given URL.
    """
    global _ORIGINAL_EXCEPTION_HANDLER

    if labels is None:
        labels = []

    ipython = get_ipython()  # noqa
    _ORIGINAL_EXCEPTION_HANDLER = _ORIGINAL_EXCEPTION_HANDLER or ipython._showtraceback

    def create_github_issue_exception_handler(exception_type, exception, traceback):
        try:
            output.clear_output()

            truncated_traceback = _strip_ansi_codes("\n".join(traceback[-25:]))
            environment_fingerprint = "\n".join(
                wrap(get_environment_fingerprint().decode("utf-8"), 100)
            )

            bug_report_query = {
                "title": BUG_REPORT_TITLE.format(
                    exception_type=str(exception_type.__name__)
                ),
                "body": BUG_REPORT_BODY.format(
                    traceback=truncated_traceback,
                    environment_fingerprint=environment_fingerprint,
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
                        traceback=truncated_traceback,
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
