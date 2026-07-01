"""
Maps a confidence score to one of the three transparency label variants
defined in planning.md. Thresholds are asymmetric on purpose — see planning.md
for the false-positive reasoning.
"""

AI_THRESHOLD = 0.75
HUMAN_THRESHOLD = 0.35

LABELS = {
    "likely_ai": (
        "This content shows strong indicators of AI generation. Our system is "
        "highly confident in this assessment based on multiple analysis signals."
    ),
    "likely_human": (
        "This content shows strong indicators of human authorship. Our system "
        "found no significant markers of AI generation."
    ),
    "uncertain": (
        "We're unable to confidently determine whether this content is "
        "AI-generated or human-written. Treat this classification as inconclusive."
    ),
}


def get_attribution(confidence: float) -> str:
    """Returns the internal attribution key: 'likely_ai' | 'likely_human' | 'uncertain'."""
    if confidence >= AI_THRESHOLD:
        return "likely_ai"
    if confidence <= HUMAN_THRESHOLD:
        return "likely_human"
    return "uncertain"


def get_label_text(confidence: float) -> str:
    """Returns the exact user-facing label text for a given confidence score."""
    return LABELS[get_attribution(confidence)]