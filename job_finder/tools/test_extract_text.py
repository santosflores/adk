import pytest

from .main import extract_text
from google.genai import types


@pytest.mark.parametrize(
    "value, expected",
    [
        ("test", "test"),  # plain str
        ("  data engineer  ", "  data engineer  "),
        ("", None),  # empty str
        (None, None),  # None
    ],
)
def test_extract_from_plain_values(value, expected):
    assert extract_text(value) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("test", "test"),  # Content WITH text
        ("  data  ", "  data  "),
    ],
)
def test_extract_from_content(text, expected):
    content = types.Content(parts=[types.Part(text=text)])
    assert extract_text(content) == expected


def test_extract_from_content_without_parts():
    assert extract_text(types.Content(parts=[])) is None  # Content's empty branch
