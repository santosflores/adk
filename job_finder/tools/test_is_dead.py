import pytest

from .main import is_dead


@pytest.mark.parametrize(
    "http_code, expected",
    [
        (200, False),
        (404, True),
        (500, True),
        (0, True),
        (403, False),
        (429, False),
    ],
)
def test_is_dead(http_code, expected):
    assert is_dead(http_code) == expected
