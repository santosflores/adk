import pytest

from .main import location_matches


@pytest.mark.parametrize(
    "location, target, expected",
    [
        ("Mexico City, Mexico", "Mexico", True),
        ("London, UK", "Mexico", False),
        ("MEXICO CITY", "Mexico", True),
        ("", "Mexico", False),
    ],
)
def test_location_matches(location: str, target: str, expected: bool):
    assert location_matches(location, target) == expected
