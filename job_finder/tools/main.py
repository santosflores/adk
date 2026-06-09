"""Tools for the agents"""

from typing import Any

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
