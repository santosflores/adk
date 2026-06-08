import pytest

from .main import is_confident


@pytest.mark.parametrize(
    "confidence, expected",
    [(0.99, True), (0.95, True), (0.5, False), (0.94, False)],
)
def test_is_confident(confidence, expected):
    assert is_confident(confidence) == expected
