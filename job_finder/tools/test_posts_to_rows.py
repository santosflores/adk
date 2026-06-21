import pytest

from .main import posts_to_rows


@pytest.mark.parametrize(
    "input, expected",
    [
        (
            [
                {
                    "id": "id1",
                    "title": "title-1",
                    "url": "https://url-1",
                    "snippet": "Issue-1 snippet",
                }
            ],
            [
                ["id", "title", "url", "snippet"],
                ["id1", "title-1", "https://url-1", "Issue-1 snippet"],
            ],
        ),
        (
            [],
            [
                ["id", "title", "url", "snippet"],
            ],
        ),
        (
            [
                {
                    "id": "id1",
                    "title": "title-1",
                    "url": "https://url-1",
                    "snippet": "Issue-1 snippet",
                },
                {
                    "id": "id2",
                    "title": "title-2",
                    "url": "https://url-2",
                    "snippet": "Issue-2 snippet",
                },
            ],
            [
                ["id", "title", "url", "snippet"],
                ["id1", "title-1", "https://url-1", "Issue-1 snippet"],
                ["id2", "title-2", "https://url-2", "Issue-2 snippet"],
            ],
        ),
        (
            [
                {
                    "id": "id1",
                    "title": "title-1",
                    "url": "https://url-1",
                    "snippet": "Issue-1 snippet",
                },
                {
                    "id": "id2",
                    "title": "title-2",
                    "snippet": "Issue-2 snippet",
                },
            ],
            [
                ["id", "title", "url", "snippet"],
                ["id1", "title-1", "https://url-1", "Issue-1 snippet"],
                ["id2", "title-2", "", "Issue-2 snippet"],
            ],
        ),
    ],
)
def test_posts_to_rows(input: list, expected: list):
    result = posts_to_rows(input)
    assert result == expected
    # Add 1 to len(input) to account for the headers
    assert len(result) == len(input) + 1
