from __future__ import annotations

FORBIDDEN_SUBSTRINGS = [
    "паспорт",
    "серия",
    "номер карты",
    "cvv",
    "cvc",
    "pin",
]


def validate_message_text(text: str) -> None:
    """Very lightweight content safety check for MVP demos.

    In production this should be replaced with a formal policy engine.
    """
    low = (text or "").lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in low:
            raise ValueError(f"forbidden substring detected: {bad}")
