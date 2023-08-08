import base64
import json
import zlib

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
