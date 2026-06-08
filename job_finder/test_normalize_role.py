import pytest 

from job_finder.agent import normalize_role

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("engineer", "Engineer"),
        (" engineer ", "Engineer"),
        ("software  engineer", "Software Engineer"),
        ("", "")
    ],
)
def test_normalize_role(raw, expected):
    assert normalize_role(raw=raw) == expected