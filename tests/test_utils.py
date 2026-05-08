import pytest

from aiidalab_widgets_base import utils


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1 3 5 7..10", [0, 2, 4, 6, 7, 8, 9]),
        (
            "1,2,3 4 5 7..10 12 14 ; 15 33 .. 35 40, 42",
            [0, 1, 2, 3, 4, 6, 7, 8, 9, 11, 13, 14, 32, 33, 34, 39, 41],
        ),
        ("", []),
    ],
)
def test_string_range_to_list_accepts_flexible_separators(value, expected):
    assert utils.string_range_to_list(value) == (expected, True)


@pytest.mark.parametrize("value", ["1..", "..3", "5..3", "1 two 3"])
def test_string_range_to_list_rejects_invalid_ranges(value):
    assert utils.string_range_to_list(value) == ([], False)
