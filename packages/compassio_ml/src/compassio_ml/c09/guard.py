"""Versioned, opt-in input defense around the UNMODIFIED frozen ML v2 classifier.

The raw and normalized predictions remain visible. Review status is not a negative
classification and must never be counted as an attack successfully prevented.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from compassio_ml.c09.attacks import CONFUSABLES
from compassio_ml.model_v2.artifact import ExperimentalClassifier

VERSION = "c09-input-guard-v1"
MAX_CONFUSABLE_FRACTION = 0.02
SCORE_SHIFT_REVIEW = 0.03
REVERSE = {v: k for k, v in CONFUSABLES.items()}
REMOVABLE = frozenset("\u200b\u2060\ufeff\u00ad")
NEGATIONS = frozenset({"no", "not", "never", "without", "cannot", "neither", "nor", "non"})
# Keep numeric/financial spelling EXACT, including locale separators and signs.
NUMERIC = re.compile(
    r"[+\-\u2212]?\d(?:[\d.,'\u2019 \t\u00a0\u202f\uff0c\uff0e\u066b\u066c]*\d)?(?:[%\u2030])?"
)
TOKENS = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class Normalized:
    text: str
    reasons: tuple[str, ...]
    ambiguous: bool


def normalize(text: str) -> Normalized:
    """Idempotent NFC + narrowly scoped sanitation; never strip accents or joiners.

    Numeric spans are shielded byte-for-byte. Confusables are mapped ONLY in mixed
    ASCII/Cyrillic tokens with a small document-level replacement budget. Whole-script
    Cyrillic, Arabic, Urdu, meaningful joiners and unsupported controls are retained.
    """
    reasons: set[str] = set()
    ambiguous = False
    letters = sum(c.isalpha() for c in text)
    # Pre-count the complete eligible map. All-or-nothing avoids incremental mapping
    # on repeated calls (and therefore guarantees idempotence when over budget).
    cleaned = unicodedata.normalize("NFC", text)
    latin = "A-Za-z" + "".join(REVERSE)
    cleaned = re.sub(rf"(?<=[{latin}])[\u200b\u2060\ufeff\u00ad]+(?=[{latin}])", "", cleaned)
    cleaned = re.sub(rf"(?<!\S)[\u200b\u2060\ufeff\u00ad]+(?=[{latin}])", "", cleaned)
    candidates = [
        m
        for m in TOKENS.finditer(cleaned)
        if any(c.isascii() and c.isalpha() for c in m.group())
        and any(c in REVERSE for c in m.group())
        and all((c.isascii() and c.isalpha()) or c in REVERSE for c in m.group())
    ]
    total = sum(sum(c in REVERSE for c in m.group()) for m in candidates)
    mapping_allowed = total <= int(letters * MAX_CONFUSABLE_FRACTION)
    if total and not mapping_allowed:
        reasons.add("confusable_limit")
        ambiguous = True

    def segment(value: str) -> str:
        nonlocal ambiguous
        value = unicodedata.normalize("NFC", value)
        # Remove only inside ASCII/mapped-Latin words. Else preserve and request review.
        chars: list[str] = []
        for i, c in enumerate(value):
            if c in REMOVABLE:
                left = next((x for x in reversed(chars) if x not in REMOVABLE), "")
                right = next((x for x in value[i + 1 :] if x not in REMOVABLE), "")
                right_latin = bool(right) and (
                    (right.isascii() and right.isalpha()) or right in REVERSE
                )
                left_latin = (left.isascii() and left.isalpha()) or left in REVERSE
                if right_latin and (left_latin or not left or left.isspace()):
                    left_word = re.search(r"[^\W\d_]+\Z", "".join(chars))
                    word = (
                        "".join(REVERSE.get(x, x) for x in left_word.group()).lower()
                        if left_word
                        else ""
                    )
                    if word not in NEGATIONS:
                        reasons.add("invisible_removed")
                        continue
                    reasons.add("retained_negation_boundary")
                ambiguous = True
                reasons.add("unsupported_invisible")
            elif unicodedata.category(c) in ("Cf", "Cc", "Cs") and c not in "\n\r\t":
                ambiguous = True
                reasons.add("retained_control_or_joiner")
            chars.append(c)
        value = "".join(chars)

        def token(m: re.Match[str]) -> str:
            nonlocal ambiguous
            word = m.group()
            mapped = sum(c in REVERSE for c in word)
            mixed = any(c.isascii() and c.isalpha() for c in word)
            supported = all((c.isascii() and c.isalpha()) or c in REVERSE for c in word)
            if mapped and mixed:
                if mapping_allowed and supported:
                    reasons.add("mixed_script_confusable")
                    return "".join(REVERSE.get(c, c) for c in word)
                ambiguous = True
                reasons.add("retained_mixed_script")
            return word

        value = TOKENS.sub(token, value)
        # Presentation forms of sentence punctuation, not financial separators.
        value = value.translate(str.maketrans("\uff0c\uff1b", ",;"))
        # Punctuation/whitespace is never deleted between words.
        value = re.sub(r"\s+", " ", value)
        return value

    # Match numeric spans against original, BEFORE any normalization.
    pieces: list[str] = []
    start = 0
    for m in NUMERIC.finditer(text):
        pieces.extend((segment(text[start : m.start()]), m.group()))
        start = m.end()
    pieces.append(segment(text[start:]))
    result = "".join(pieces).strip()
    if result != text:
        reasons.add("normalized")
    return Normalized(result, tuple(sorted(reasons)), ambiguous)


def validate_reporting(amount: Decimal | None, currency: str | None) -> None:
    """Validate an optional isolated reporting pair; NEVER send it into the model.

    Decimal only (no float coercion), finite and nonnegative; require a currency for
    an amount. The three-letter syntax is not a claim of ISO registry membership.
    """
    if amount is not None and (
        not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0
    ):
        raise ValueError("amount must be a finite nonnegative Decimal")
    if currency is not None and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter uppercase code")
    if (amount is None) != (currency is None):
        raise ValueError("amount and currency must be supplied together")


@dataclass(frozen=True)
class GuardPrediction:
    raw_score: float
    guarded_score: float
    threshold: float
    is_climate_related: bool
    unstable_input: bool
    requires_review: bool
    outcome: Literal["consistent", "requires_review", "unstable_input"]
    normalized_fields: tuple[str, str]
    reasons: tuple[str, ...]
    guard_version: str = VERSION


class GuardedClassifier:
    """Adapter only: existing model weights, vectorizer and threshold are never mutated."""

    def __init__(self, classifier: ExperimentalClassifier) -> None:
        self.classifier = classifier

    def predict(
        self,
        title: str | None,
        description: str | None,
        *,
        amount: Decimal | None = None,
        currency: str | None = None,
    ) -> GuardPrediction:
        validate_reporting(amount, currency)
        if any(t is not None and not isinstance(t, str) for t in (title, description)):
            raise ValueError("text fields must be strings or None")
        fields = (title or "", description or "")
        for text, maximum in zip(fields, (1000, 20000), strict=True):
            if not isinstance(text, str) or len(text) > maximum or "\x00" in text:
                raise ValueError("invalid or oversized text field")
        normalized = tuple(normalize(t) for t in fields)
        changed = (normalized[0].text, normalized[1].text)
        if not any(t.strip() for t in changed):
            raise ValueError("empty normalized input")
        raw = self.classifier.predict(*fields)
        guarded = self.classifier.predict(*changed) if changed != fields else raw
        unstable = (
            raw.is_climate_related != guarded.is_climate_related
            or abs(raw.label_score - guarded.label_score) > SCORE_SHIFT_REVIEW
        )
        review = unstable or any(n.ambiguous for n in normalized)
        reasons = tuple(sorted({reason for n in normalized for reason in n.reasons}))
        return GuardPrediction(
            raw.label_score,
            guarded.label_score,
            raw.threshold,
            guarded.is_climate_related,
            unstable,
            review,
            "unstable_input" if unstable else "requires_review" if review else "consistent",
            changed,
            reasons,
        )
