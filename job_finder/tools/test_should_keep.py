import pytest

from .main import should_keep


@pytest.mark.parametrize(
    "status_code, country, is_remote, target, expected",
    [
        (404, "US", True, "US", False),               # dead beats remote + match
        (200, "US", True, "Mexico", True),            # remote beats country miss
        (200, None, False, "Mexico", True),           # unknown country -> keep
        (200, "Mexico", False, "Mexico", True),       # in-locale
        (200, "United Kingdom", False, "Mexico", False),  # out-of-locale
    ],
)
def test_should_keep(status_code, country, is_remote, target, expected):
    assert should_keep(status_code, country, is_remote, target) == expected
