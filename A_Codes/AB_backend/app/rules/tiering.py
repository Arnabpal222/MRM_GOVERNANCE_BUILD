"""R1 Risk tiering (BRD §7). Thresholds are passed in from policy — never constants."""
from dataclasses import dataclass

TIERS = ("High", "Medium", "Low")
TIERING_QUESTIONS = ("q_materiality", "q_complexity", "q_reliance", "q_regulatory_use")
TIERING_QUESTION_TEXT = {
    "q_materiality": "How large is the financial exposure or balance the model drives?",
    "q_complexity": "How complex is the method, data or number of components?",
    "q_reliance": "How much do decisions depend on the output without other checks?",
    "q_regulatory_use": "Is the output used in regulatory capital, provisioning or stress-test submissions?",
}


@dataclass(frozen=True)
class TierResult:
    score: int
    tier: str


def validate_answers(answers: dict[str, int | None]) -> list[str]:
    errors = []
    for q in TIERING_QUESTIONS:
        v = answers.get(q)
        if v is None:
            errors.append(f"{q} is required.")
        elif v not in (1, 2, 3):
            errors.append(f"{q} must be 1, 2 or 3 (got {v}).")
    return errors


def calculate_tier(answers: dict[str, int], high_min: int, medium_min: int) -> TierResult:
    """Tier score = sum of the four answers; High if >= high_min, Medium if >= medium_min, else Low."""
    score = sum(answers[q] for q in TIERING_QUESTIONS)
    if score >= high_min:
        tier = "High"
    elif score >= medium_min:
        tier = "Medium"
    else:
        tier = "Low"
    return TierResult(score=score, tier=tier)


def effective_tier(calculated: str, override: str | None) -> str:
    """An override replaces the calculated tier for display and rules; the calculated tier is kept."""
    return override or calculated
