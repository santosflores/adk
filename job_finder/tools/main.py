"""Tools for the agents"""

from typing import Any, Callable

CONFIDENCE_THRESHOLD = 0.95


def normalize_role(raw: str) -> str:
    return " ".join(raw.split()).title()


def is_confident(confidence: float) -> bool:
    return confidence >= CONFIDENCE_THRESHOLD


def extract_text(node_input: Any) -> str | None:
    from google.genai import types

    if isinstance(node_input, types.Content):
        raw = node_input.parts[0].text if node_input.parts else ""
    else:
        raw = node_input if node_input else ""
    return raw if raw else None


def extract_ashby_link(link: str) -> tuple[str, str] | None:
    parts = link.split("/")
    if len(parts) < 5 or not parts[4]:
        return None
    job_post_id = parts[4]
    return (job_post_id, "/".join(parts[:5]))


def parse_page(
    organic_results: list[dict],
    extract_link: Callable[[str], tuple[str, str] | None],
) -> list[dict]:
    posts = []
    for job_post in organic_results:
        result = extract_link(job_post["link"])
        if result is None:
            continue
        job_post_id, url = result
        posts.append(
            {
                "title": job_post["title"],
                "url": url,
                "snippet": job_post["snippet"],
                "id": job_post_id,
            }
        )
    return posts
