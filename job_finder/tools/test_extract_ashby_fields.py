import pytest

from .main import extract_ashby_fields


@pytest.mark.parametrize(
    "job, expected",
    [
        (
            {"isRemote": True, "address": {"postalAddress": {"addressCountry": "United States"}}},
            ("United States", True),
        ),
        (
            {"isRemote": False, "address": {"postalAddress": {"addressCountry": "United Kingdom"}}},
            ("United Kingdom", False),
        ),
        (
            {"isRemote": None, "address": {"postalAddress": {"addressCountry": "United States"}}},
            ("United States", False),
        ),
        (
            {"isRemote": True},
            (None, True),
        ),
    ],
)
def test_extract_ashby_fields(job, expected):
    assert extract_ashby_fields(job) == expected
