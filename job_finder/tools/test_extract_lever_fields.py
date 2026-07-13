import pytest

from .main import extract_lever_fields

@pytest.mark.parametrize(
    "node_input, expected",
    [
        (
            {"country": "US", "workplaceType": "remote"},
            ("US", True),
        ),
        (
            {"country": "US", "workplaceType": "hybrid"},
            ("US", True),
        ),
        (
            {"country": "US", "workplaceType": "onsite"},
            ("US", False),
        ),
        (
            {},
            (None, False),
        ),
    ],
)
def test_extract_lever_fields(node_input, expected):
    assert extract_lever_fields(node_input) == expected
