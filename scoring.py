"""
Combines Signal 1 (Groq LLM) and Signal 2 (stylometrics) into one confidence score.
Weighting is defined in planning.md: LLM signal weighted higher because it reasons
about meaning; stylometrics is a supporting heuristic.
"""

from signals import get_llm_signal
from stylometrics import get_stylometric_signal

LLM_WEIGHT = 0.6
STYLOMETRIC_WEIGHT = 0.4


def score_content(text: str) -> dict:
    """
    Runs both signals and combines them.

    Returns:
        {
            "confidence": float 0.0-1.0,
            "llm_score": float,
            "stylometric_score": float,
            "llm_reasoning": str,
            "stylometric_detail": {sentence_variance_score, ttr_score, punctuation_score},
        }
    """
    llm_result = get_llm_signal(text)
    style_result = get_stylometric_signal(text)

    confidence = (
        LLM_WEIGHT * llm_result["llm_score"]
        + STYLOMETRIC_WEIGHT * style_result["stylometric_score"]
    )
    confidence = round(max(0.0, min(1.0, confidence)), 3)

    return {
        "confidence": confidence,
        "llm_score": llm_result["llm_score"],
        "stylometric_score": style_result["stylometric_score"],
        "llm_reasoning": llm_result["reasoning"],
        "stylometric_detail": {
            "sentence_variance_score": style_result["sentence_variance_score"],
            "ttr_score": style_result["ttr_score"],
            "punctuation_score": style_result["punctuation_score"],
        },
    }


if __name__ == "__main__":
    # The 4 required test cases from the M4 spec, spanning the confidence range.
    test_cases = {
        "clearly_ai": (
            "Artificial intelligence represents a transformative paradigm shift in modern "
            "society. It is important to note that while the benefits of AI are numerous, "
            "it is equally essential to consider the ethical implications. Furthermore, "
            "stakeholders across various sectors must collaborate to ensure responsible "
            "deployment."
        ),
        "clearly_human": (
            "ok so i finally tried that new ramen place downtown and honestly? "
            "underwhelming. the broth was fine but they put WAY too much sodium in it and "
            "i was thirsty for like three hours after. my friend got the spicy version and "
            "said it was better. probably won't go back unless someone drags me there"
        ),
        "borderline_formal_human": (
            "The relationship between monetary policy and asset price inflation has been "
            "extensively studied in the literature. Central banks face a fundamental "
            "tension between their mandate for price stability and the unintended "
            "consequences of prolonged low interest rates on equity and real estate "
            "valuations."
        ),
        "borderline_edited_ai": (
            "I've been thinking a lot about remote work lately. There are genuine "
            "tradeoffs — flexibility and no commute on one side, isolation and blurred "
            "work-life boundaries on the other. Studies show productivity varies widely "
            "by individual and role type."
        ),
    }

    for label, text in test_cases.items():
        result = score_content(text)
        print(f"\n--- {label} ---")
        print(f"confidence: {result['confidence']}")
        print(f"  llm_score: {result['llm_score']}")
        print(f"  stylometric_score: {result['stylometric_score']}")
        print(f"  stylometric_detail: {result['stylometric_detail']}")