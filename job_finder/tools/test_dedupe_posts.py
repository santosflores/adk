import pytest

from .main import dedupe_posts
from typing import Any


@pytest.mark.parametrize(
    "node_input, expected",
    [
        ([], []),
        (
            [
                {"id": "a"},
                {"id": "b"},
            ],
            [
                {"id": "a"},
                {"id": "b"},
            ],
        ),
        (
            [
                {"id": "a", "snippet": "snippet-test-1"},
                {"id": "a", "snippet": "snippet-test-2"},
                {"id": "b", "snippet": "snippet-test-b"},
            ],
            [
                {"id": "a", "snippet": "snippet-test-1"},
                {"id": "b", "snippet": "snippet-test-b"},
            ],
        ),
        (
            [
                {"id": "a", "snippet": "snippet-test-1"},
                {"id": "b", "snippet": "snippet-test-b"},
                {"id": "a", "snippet": "snippet-test-2"},
            ],
            [
                {"id": "a", "snippet": "snippet-test-1"},
                {"id": "b", "snippet": "snippet-test-b"},
            ],
        ),
    ],
)
def test_dedupe_posts(node_input: Any, expected: list[dict]):
    assert dedupe_posts(node_input) == expected
