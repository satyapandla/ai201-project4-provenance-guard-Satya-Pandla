"""
Signal 2: stylometric heuristics.

Three pure-Python metrics, each scaled to 0-1 where 1.0 = "more AI-like" on that
metric, then averaged into a single stylometric_score. No external libraries.

Per planning.md: AI text tends toward uniformity (consistent sentence length,
narrower vocabulary, more formulaic transitional punctuation). Human writing is
messier. Each metric below encodes that assumption — and each has a documented
blind spot (see planning.md's "Where this will probably get it wrong" section).
"""

import re
import statistics

# Regex-based sentence splitter — good enough for this project, not NLP-grade.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD_SPLIT = re.compile(r"[A-Za-z']+")
_FORMAL_PUNCT = re.compile(r"[,;:]")


def _sentences(text: str) -> list:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _words(text: str) -> list:
    return [w.lower() for w in _WORD_SPLIT.findall(text)]


def sentence_length_variance_score(sentences: list) -> float:
    """Low variance in sentence length (in words) => more AI-like => score closer to 1."""
    if len(sentences) < 3:
        # 2 sentences produces wildly noisy variance (confirmed by testing: a real
        # AI-generated 2-sentence excerpt scored as "high variance" purely because
        # one sentence happened to be longer than the other). Need at least 3
        # sentences before this metric means anything.
        return 0.5

    lengths = [len(_words(s)) for s in sentences]
    variance = statistics.variance(lengths)

    # Scale: variance of 0 -> score 1.0. Variance of ~8+ (typical human variability)
    # -> score drops toward 0. Tunable constant, not derived from real training data.
    score = 1 / (1 + variance / 8)
    return max(0.0, min(1.0, score))


def type_token_ratio_score(words: list) -> float:
    """Lower vocabulary diversity (more repetition) => more AI-like => score closer to 1."""
    if len(words) < 40:
        # Below ~40 words, TTR is dominated by noise — almost any short text has
        # high diversity simply because there hasn't been room for repetition yet.
        return 0.5

    ttr = len(set(words)) / len(words)
    # Invert: high diversity (ttr near 1) => human-like => low AI score.
    score = 1 - ttr
    return max(0.0, min(1.0, score))


def punctuation_density_score(text: str, sentences: list) -> float:
    """Higher density of formal transitional punctuation => more AI-like."""
    if not sentences:
        return 0.5

    formal_marks = len(_FORMAL_PUNCT.findall(text))
    density = formal_marks / len(sentences)

    # 4+ formal marks per sentence on average is unusually dense -> caps score at 1.0.
    score = min(1.0, density / 4)
    return score


def get_stylometric_signal(text: str) -> dict:
    """
    Signal 2: combines three stylometric metrics into one score.

    Returns:
        {
            "stylometric_score": float 0.0-1.0,
            "sentence_variance_score": float,
            "ttr_score": float,
            "punctuation_score": float,
        }
    """
    sentences = _sentences(text)
    words = _words(text)

    sv_score = sentence_length_variance_score(sentences)
    ttr_score = type_token_ratio_score(words)
    punct_score = punctuation_density_score(text, sentences)

    # Equal weighting across the three sub-metrics — no strong reason to favor one
    # over another at this stage; revisit if M4 testing shows one is noisier.
    stylometric_score = (sv_score + ttr_score + punct_score) / 3

    return {
        "stylometric_score": round(stylometric_score, 3),
        "sentence_variance_score": round(sv_score, 3),
        "ttr_score": round(ttr_score, 3),
        "punctuation_score": round(punct_score, 3),
    }


if __name__ == "__main__":
    test_inputs = [
        "The sun dipped below the horizon, painting the sky in hues of amber and rose. "
        "I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.",

        "Artificial intelligence represents a transformative paradigm shift in modern "
        "society. It is important to note that while the benefits of AI are numerous, "
        "it is equally essential to consider the ethical implications.",

        "ok so i finally tried that new ramen place downtown and honestly? underwhelming. "
        "the broth was fine but they put WAY too much sodium in it.",
    ]

    for i, text in enumerate(test_inputs, 1):
        result = get_stylometric_signal(text)
        print(f"\n--- Test input {i} ---")
        print(f"Text: {text[:60]}...")
        for k, v in result.items():
            print(f"{k}: {v}")