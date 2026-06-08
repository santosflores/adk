"""Tools for the agents"""

CONFIDENCE_THRESHOLD = 0.95

def normalize_role(raw: str):
    return " ".join(raw.split()).title()

def is_confident(confidence: float) -> bool:
    return confidence >= CONFIDENCE_THRESHOLD