import pytest

from .main import parse_page, extract_ashby_link
from typing import Any


@pytest.mark.parametrize(
    "node_input, expected",
    [
        ([], []),
        (
            [
                {
                    "position": 1,
                    "title": "Partner Engineer @ Replit",
                    "link": "https://jobs.ashbyhq.com/replit/a6934e30-8064-441b-9534-85278f509794/application",
                    "snippet": "...",
                    "favicon": "...",
                }
            ],
            [
                {
                    "title": "Partner Engineer @ Replit",
                    "url": "https://jobs.ashbyhq.com/replit/a6934e30-8064-441b-9534-85278f509794",
                    "snippet": "...",
                    "id": "a6934e30-8064-441b-9534-85278f509794",
                }
            ],
        ),
        (
            [
                {
                    "position": 1,
                    "title": "Partner Engineer @ Replit",
                    "link": "https://jobs.ashbyhq.com/replit",
                    "snippet": "...",
                    "favicon": "...",
                }
            ],
            [],
        ),
        (
            [
                {
                    "position": 1,
                    "title": "Partner Engineer @ Replit",
                    "link": "https://jobs.ashbyhq.com/replit/",
                    "snippet": "...",
                    "favicon": "...",
                }
            ],
            [],
        ),
        (
            [
                {
                    "position": 6,
                    "title": "Partner Solutions Engineer @ Notion",
                    "link": "https://jobs.ashbyhq.com/notion/a6a91521-87cd-41aa-b800-24dc8808d375/application?source=LinkedIn",
                    "snippet": "...",
                    "favicon": "...",
                }
            ],
            [
                {
                    "title": "Partner Solutions Engineer @ Notion",
                    "url": "https://jobs.ashbyhq.com/notion/a6a91521-87cd-41aa-b800-24dc8808d375",
                    "snippet": "...",
                    "id": "a6a91521-87cd-41aa-b800-24dc8808d375",
                }
            ],
        ),
    ],
)
def test_parse_page_ashby_happy_path(node_input: Any, expected: dict):
    assert parse_page(node_input, extract_ashby_link) == expected
