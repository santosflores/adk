import pytest

from .main import extract_greenhouse_fields


@pytest.mark.parametrize(
    "job, expected",
    [
        (
            {
                "location": {"name": "San Francisco Bay Area"},
                "offices": [{"location": "San Francisco, California, United States"}],
            },
            ("San Francisco, California, United States", False),
        ),
        (
            {"location": {"name": "Remote, US"}, "offices": []},
            ("Remote, US", True),
        ),
        (
            {
                "location": {"name": "San Francisco Bay Area or Remote (U.S.)"},
                "offices": [{"location": None}],
            },
            ("San Francisco Bay Area or Remote (U.S.)", True),
        ),
        (
            {"location": {"name": "Dublin, IE"}, "offices": [{"location": "Dublin, IE"}]},
            ("Dublin, IE", False),
        ),
        (
            {},
            (None, False),
        ),
    ],
)
def test_extract_greenhouse_fields(job, expected):
    assert extract_greenhouse_fields(job) == expected
