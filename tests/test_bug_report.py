import base64
import json
import zlib

# TODO: this is a workaround for a import issue of aiida-core fixtures..
# from aiidalab_widgets_base.bug_report import (
#     get_environment_fingerprint,
#     parse_environment_fingerprint,
# )


def test_fingerprint_parser():
    """Test get_environment_fingerprint function and parse it out."""
    from aiidalab_widgets_base.bug_report import (
        get_environment_fingerprint,
        parse_environment_fingerprint,
    )

    encoding = "utf-8"
    fingerprint = get_environment_fingerprint(encoding)

    # Parse the fingerprint.
    data = parse_environment_fingerprint(fingerprint)

    # To test, manually generate the fingerprint and compare it to the output of the parser.
    json_data = json.dumps(data, separators=(",", ":"))
    got = base64.urlsafe_b64encode(zlib.compress(json_data.encode(encoding), level=9))

    assert got == fingerprint


def test_fingerprint_parser_for_old_aiidalab(monkeypatch):
    """I mocked the find_installed_packages function to return the old type of aiidalab <= 22.11.0.
    So we can sure for the backward compatibility of the fingerprint parser.
    """
    from aiidalab.utils import FIND_INSTALLED_PACKAGES_CACHE, Package

    from aiidalab_widgets_base.bug_report import (
        get_environment_fingerprint,
        parse_environment_fingerprint,
    )

    monkeypatch.setattr(
        "aiidalab.utils.find_installed_packages", lambda: [Package("dummy", "0.0.1")]
    )
    FIND_INSTALLED_PACKAGES_CACHE.clear()  # clear the cache

    encoding = "utf-8"
    fingerprint = get_environment_fingerprint(encoding)

    # Parse the fingerprint.
    data = parse_environment_fingerprint(fingerprint)

    # To test, manually generate the fingerprint and compare it to the output of the parser.
    json_data = json.dumps(data, separators=(",", ":"))
    got = base64.urlsafe_b64encode(zlib.compress(json_data.encode(encoding), level=9))

    assert got == fingerprint
