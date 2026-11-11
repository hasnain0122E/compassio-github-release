"""Bounded, sanitised model input (the same title/description layout the models were trained on)."""

import hashlib
import unicodedata

TITLE_MAX = 1_000
DESCRIPTION_MAX = 20_000
SEPARATOR = " \n "  # identical to compassio_ml.modeling.features.SEPARATOR


class InvalidInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sanitize(value: str | None, limit: int, field: str) -> str:
    """Strip, normalise to NFC and drop control characters (newline and tab are kept)."""
    if value is None:
        return ""
    if "\x00" in value:
        raise InvalidInputError("invalid_text", f"{field} contains a NUL character")
    text = unicodedata.normalize("NFC", value)
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c)[0] != "C").strip()
    if len(text) > limit:
        raise InvalidInputError("text_too_long", f"{field} exceeds {limit} characters")
    return text


def model_text(title: str, description: str) -> str:
    """Mirror of compassio_ml.modeling.features.build_text(..., 'title_description')."""
    return f"{title}{SEPARATOR}{description}" if title and description else (title or description)


def prepare(title: str | None, description: str | None) -> tuple[str, str, str]:
    t = sanitize(title, TITLE_MAX, "title")
    d = sanitize(description, DESCRIPTION_MAX, "description")
    if not t and not d:
        raise InvalidInputError("empty_input", "title and description are both empty")
    return t, d, model_text(t, d)


def input_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
