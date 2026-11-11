"""Rio Marker parsing, text cleaning and retrospective diagnostics (artificial inputs only)."""

import pytest

from compassio_ml.research.labels import SCORE_MEANING, parse_rio_marker
from compassio_ml.research.retrospective import MAX_EVENT_YEAR, diagnose, later_years
from compassio_ml.research.text import (
    STEP_ENTITIES,
    STEP_HTML,
    STEP_NFC,
    STEP_SENTINEL,
    STEP_WHITESPACE,
    STEP_ZERO_WIDTH,
    clean_text,
    word_count,
)


# ---------------------------------------------------------------- Rio Marker
@pytest.mark.parametrize(
    ("raw", "overall", "mitigation", "adaptation", "climate"),
    [
        ("2,0,2", 2, 0, 2, True),  # paper Table 1: drought-resistant rice
        ("2,2,0", 2, 2, 0, True),  # paper Table 1: electric/hybrid vehicles
        ("0,0,0", 0, 0, 0, False),
        ("1,1,1", 1, 1, 1, True),
    ],
)
def test_rio_fields_follow_paper_order(
    raw: str, overall: int, mitigation: int, adaptation: int, climate: bool
) -> None:
    marker = parse_rio_marker(raw)

    assert marker is not None
    assert marker.rio_overall == overall
    assert marker.rio_mitigation == mitigation
    assert marker.rio_adaptation == adaptation
    assert marker.is_climate_related is climate


def test_score_meanings_match_paper() -> None:
    assert SCORE_MEANING == {
        0: "not targeted",
        1: "significant objective",
        2: "principal objective",
    }


@pytest.mark.parametrize("raw", ["3,0,0", "-1,0,0", "1,1", "1,1,1,1", "a,b,c", "1;0;1", "1.0,0,1"])
def test_invalid_rio_values_raise(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_rio_marker(raw)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_missing_rio_is_none_not_negative(raw: str | None) -> None:
    assert parse_rio_marker(raw) is None


def test_overall_max_relationship_is_checked_not_assumed() -> None:
    inconsistent = parse_rio_marker("1,2,0")  # parses: valid scores, unusual relationship

    assert inconsistent is not None
    assert not inconsistent.overall_is_max
    consistent = parse_rio_marker("2,1,2")
    assert consistent is not None and consistent.overall_is_max


# ---------------------------------------------------------------- text cleaning
def test_whitespace_and_invisible_characters() -> None:
    nbsp, zwsp = chr(0x00A0), chr(0x200B)
    result = clean_text(f"  Example{nbsp}solar\tplant{zwsp}  project  ")

    assert result.value == "Example solar plant project"
    assert result.steps == (STEP_ZERO_WIDTH, STEP_WHITESPACE)


def test_nfc_normalization_preserves_meaningful_characters() -> None:
    decomposed = "Cafe" + chr(0x0301)  # e + combining acute
    result = clean_text(f"{decomposed} 10 m{chr(0x00B2)} {chr(0xFF08)}example{chr(0xFF09)}")

    assert result.value == "Caf" + chr(0x00E9) + " 10 m" + chr(0x00B2) + " " + chr(
        0xFF08
    ) + "example" + chr(0xFF09)
    assert STEP_NFC in result.steps  # NFC composes; NFKC would have rewritten superscript/fullwidth


def test_html_removed_but_text_preserved() -> None:
    result = clean_text("<p>Example <b>hydropower</b> loan</p><script>alert(1)</script><br>Phase 2")

    assert result.value == "Example hydropower loan Phase 2"
    assert STEP_HTML in result.steps


def test_entities_unescaped_without_tags() -> None:
    result = clean_text("Roads &amp; bridges &#8211; example")

    assert result.value == "Roads & bridges " + chr(0x2013) + " example"
    assert result.steps == (STEP_ENTITIES,)


@pytest.mark.parametrize("raw", ["nan", "NULL", " n/a ", "-", ""])
def test_sentinels_become_null(raw: str) -> None:
    result = clean_text(raw)

    assert result.value is None
    assert STEP_SENTINEL in result.steps


def test_no_truncation_or_case_change_and_idempotent() -> None:
    text = "Example DESCRIPTION " * 5000  # 100,000 characters
    once = clean_text(text)
    twice = clean_text(once.value)

    assert once.value == text.strip()
    assert twice.value == once.value
    assert twice.steps == ()


def test_none_and_word_count() -> None:
    assert clean_text(None).value is None
    assert clean_text(None).steps == ()
    assert word_count("one two  three") == 3
    assert word_count(None) == 0


# ---------------------------------------------------------------- retrospective diagnostic
def test_later_year_bounds() -> None:
    text = "Signed in 2010, completed in 2015, repaid by 2035."

    assert later_years(text, 2010) == [2015]  # 2035 is contractual, beyond MAX_EVENT_YEAR
    assert MAX_EVENT_YEAR == 2023
    assert later_years("Signed in 2010.", 2010) == []


def test_signals_and_warning() -> None:
    flags = diagnose("The example plant was completed and handed over in 2016.", 2012)

    assert flags.later_year_mention
    assert flags.completion_language
    assert flags.retrospective_text_warning
    assert flags.signals == ("later_year_mention", "completion_language")


def test_disbursement_and_status_language() -> None:
    assert diagnose("The loan was fully disbursed.", 2012).disbursement_language
    assert diagnose("The project was later cancelled.", 2012).status_outcome_language
    assert diagnose("As of March 2019, works continue.", 2012).status_outcome_language


def test_label_revealing_terms_are_separate_from_warning() -> None:
    flags = diagnose("An example programme on climate change adaptation.", 2012)

    assert flags.label_revealing_terms
    assert not flags.retrospective_text_warning


def test_clean_text_without_signals() -> None:
    flags = diagnose("China agrees to finance an example water project.", 2012)

    assert not flags.retrospective_text_warning
    assert flags.signals == ()
    assert not diagnose(None, None).retrospective_text_warning
