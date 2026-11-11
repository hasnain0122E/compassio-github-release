"""Artificial example_* fixtures test engineering only, never model evidence."""

import pytest

from compassio_ml.c09.attacks import KINDS, Edit, attack, budget, distance, replay
from compassio_ml.c09.guard import normalize, validate_reporting


@pytest.mark.parametrize("kind", KINDS)
def test_budget_receipts_and_determinism(kind: str) -> None:
    fields = ("example_project " + "project support,development " * 20, "not solar USD 1,234.50")
    a = attack(fields, kind, 9)
    assert a == attack(fields, kind, 9)
    assert a.fields == replay(fields, a.edits)
    assert a.edit_distance * 50 <= a.eligible_characters
    assert a.fields[1] == fields[1]


def test_budget_protects_short_financial_negation_and_climate_inputs() -> None:
    assert budget(("no solar USD 123.50", ""))[1] == 0
    assert not attack(("project", ""), "confusable", 0).edits
    with pytest.raises(ValueError, match="budget"):
        replay(("project", ""), (Edit(0, 0, "p", "x"),))
    with pytest.raises(ValueError, match="protected"):
        replay(("project " * 100 + "123", ""), (Edit(0, 800, "1", "2"),))


@pytest.mark.parametrize(
    ("a", "b", "d"),
    [
        ("", "", 0),
        ("abc", "abxc", 1),
        ("abc", "axc", 1),
        ("abc", "ac", 1),
        ("abc", "xyz", 3),
        ("aab", "abb", 1),
    ],
)
def test_distance(a: str, b: str, d: int) -> None:
    assert distance(a, b, 4) == d
    assert distance(a, b, 0) == min(d, 1)


@pytest.mark.parametrize(
    "text",
    [
        "example_not solar USD 1,234.50; no reduction",
        "example_école e\u0301cole اردو عربی русский 中文",
        "example_می\u200cروم 👩\u200d🔬",
        "example_ USD 1\u00a0234,50; -2.5%; 1  000; ۱۲۳",
        "example_project " * 30 + "p\u0430y",
        "p\u0430\u200by " * 30,
        "project\u200b support \ufeffdevelopment",
        "project\u202e example_unsafe",
    ],
)
def test_unicode_idempotence(text: str) -> None:
    clean = normalize(text).text
    assert normalize(clean).text == clean


def test_no_destructive_unicode_finance_or_negation_rewrite() -> None:
    text = "example_école اردو می\u200cروم no solar USD 1\u00a0234,50 -2.5%"
    assert normalize(text).text == text
    assert normalize(text).ambiguous
    assert normalize("project\u202e support").ambiguous
    assert normalize("\u0440ay").text == "\u0440ay"
    assert normalize("\u0440ay").ambiguous
    assert normalize("USD 1\uff0c234\uff0e50").text == "USD 1\uff0c234\uff0e50"


@pytest.mark.parametrize("word", ["no", "not", "never", "without", "cannot", "neither", "nor"])
@pytest.mark.parametrize("separator", ["\u200b", "\u2060", "\ufeff", "\u00ad"])
def test_invisible_negation_boundary_requires_review(word: str, separator: str) -> None:
    text = f"example_project {word}{separator}solar"
    result = normalize(text)
    assert result.text == text
    assert result.ambiguous and "retained_negation_boundary" in result.reasons
    assert normalize(result.text).text == result.text


def test_structured_pair_validation() -> None:
    from decimal import Decimal

    validate_reporting(Decimal("123.45"), "USD")
    for value, currency in [
        (Decimal("NaN"), "USD"),
        (Decimal("-1"), "USD"),
        (Decimal("1"), None),
        (None, "USD"),
        (Decimal("1"), "usd"),
    ]:
        with pytest.raises(ValueError):
            validate_reporting(value, currency)


def test_distance_against_unbanded_reference() -> None:
    from itertools import product

    texts = ["".join(p) for n in range(4) for p in product("ab", repeat=n)]
    for a in texts:
        for b in texts:
            previous = list(range(len(b) + 1))
            for i, char in enumerate(a, 1):
                current = [i]
                for j, other in enumerate(b, 1):
                    current.append(
                        min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (char != other))
                    )
                previous = current
            for limit in range(4):
                assert distance(a, b, limit) == min(previous[-1], limit + 1)


def test_seeded_unicode_normalization_and_financial_spans() -> None:
    import random

    rng = random.Random(9009)
    atoms = [
        "example_project",
        "no",
        "not",
        "\u0430",
        "é",
        "e\u0301",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        "\u00ad",
        " ",
        "\t",
        "\n",
        "اردو",
    ]
    for _ in range(300):
        text = "".join(rng.choices(atoms, k=30)) + " USD -1\u00a0234,50"
        normalized = normalize(text).text
        assert normalize(normalized).text == normalized
        assert normalized.endswith(" USD -1\u00a0234,50")


def test_adapter_review_and_validation_contract() -> None:
    from compassio_ml.c09.guard import GuardedClassifier
    from compassio_ml.model_v2.artifact import CandidatePrediction, ExperimentalClassifier

    class ExampleModel(ExperimentalClassifier):
        def __init__(self) -> None:
            self.threshold = 0.5

        def predict(self, title: str | None, description: str | None) -> CandidatePrediction:
            score = 0.49 if "\u200b" in (title or "") else 0.51
            return CandidatePrediction(
                score >= self.threshold,
                score,
                self.threshold,
                "example_candidate",
                "development_candidate",
                "example_only",
            )

    guard = GuardedClassifier(ExampleModel())
    result = guard.predict("example_pro\u200bject", "")
    assert result.requires_review and result.unstable_input
    assert result.outcome == "unstable_input"
    assert result.raw_score == 0.49 and result.guarded_score == 0.51
    assert result.threshold == 0.5 and result.is_climate_related
    assert guard.predict("example_اردو", "").normalized_fields == ("example_اردو", "")
    for title in ("\x00", "x" * 1001, " "):
        with pytest.raises(ValueError):
            guard.predict(title, "")


def test_report_escapes_source_text(tmp_path: object) -> None:
    from pathlib import Path

    from compassio_ml.c09.report import render_html

    assert isinstance(tmp_path, Path)
    row = {
        "candidate_id": "example_id",
        "attack": "example_attack",
        "split": "assessment",
        "clean_score": 0.5,
        "perturbed_score": 0.5,
        "guarded_score": 0.5,
        "review": False,
        "query_count": 1,
        "original_fields": ["<script>example_attack</script>", ""],
        "receipt": {
            "fields": ["<script>example_attack</script>", ""],
            "edits": [],
            "edit_distance": 0,
            "eligible_characters": 0,
            "edit_percent": 0,
        },
    }
    render_html(tmp_path, {"assessment": {}}, [row])
    text = (tmp_path / "scorecard.html").read_text("utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
