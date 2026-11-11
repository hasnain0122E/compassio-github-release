"""Diagnostic for retrospective wording in project descriptions.

This is a *warning*, not proof. A flag means the text contains wording that is typical of
information written after the commitment (later-year events, completion, disbursement,
cancellation or status updates). Records are never removed because of it.

Known limitations (see docs/data/research_cleaning_spec.md):
* Lexical patterns miss paraphrases and can fire on contractual terms known at signing
  (e.g. "repaid over 20 years"). Contractual future years are therefore excluded from the
  later-year signal by the ``max_event_year`` bound (AidData tracked implementation to 2023).
* Absence of a flag does not show that the text was written at approval time.
"""

import re
from dataclasses import dataclass

MAX_EVENT_YEAR = 2023  # AidData GCDF 3.0 tracks implementation through 2023 (Guide sheet)

_YEAR = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")

SIGNALS: dict[str, re.Pattern[str]] = {
    "completion_language": re.compile(
        r"\b(?:was|were|has been|have been|had been)\s+(?:successfully\s+)?"
        r"(?:completed|finished|inaugurated|handed over|commissioned)\b"
        r"|\b(?:completion|handover|hand-over|inauguration)\s+ceremony\b"
        r"|\bofficially\s+(?:opened|completed|inaugurated)\b"
        r"|\bput\s+into\s+(?:operation|use|service)\b",
        re.IGNORECASE,
    ),
    "disbursement_language": re.compile(
        r"\b(?:was|were|had been|has been)\s+(?:fully\s+)?disbursed\b"
        r"|\bdisbursed\s+(?:a total of|in full|the)\b|\bdisbursement rate\b"
        r"|\b(?:was|were|has been|had been)\s+(?:fully\s+)?repaid\b",
        re.IGNORECASE,
    ),
    "status_outcome_language": re.compile(
        r"\b(?:was|were|has been|had been)\s+(?:later\s+)?"
        r"(?:cancell?ed|suspended|terminated|halted|abandoned|delayed)\b"
        r"|\bnever\s+(?:materiali[sz]ed|implemented|disbursed)\b"
        r"|\bas of\s+(?:(?:january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+)?(?:\d{1,2},?\s+)?20\d\d\b",
        re.IGNORECASE,
    ),
}

# Lexical cues that may reveal the research classification itself (a leakage indicator,
# reported separately; not part of the retrospective warning).
LABEL_REVEALING = re.compile(
    r"\bclimate[- ]change\b|\bclimate (?:resilien\w*|adaptation|mitigation|finance|action)\b"
    r"|\bgreenhouse gas\w*\b|\blow[- ]carbon\b|\bcarbon (?:emission\w*|neutral\w*|sink\w*)\b"
    r"|\brenewable energy\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RetrospectiveFlags:
    later_year_mention: bool
    completion_language: bool
    disbursement_language: bool
    status_outcome_language: bool
    label_revealing_terms: bool

    @property
    def retrospective_text_warning(self) -> bool:
        return (
            self.later_year_mention
            or self.completion_language
            or self.disbursement_language
            or self.status_outcome_language
        )

    @property
    def signals(self) -> tuple[str, ...]:
        names = (
            "later_year_mention",
            "completion_language",
            "disbursement_language",
            "status_outcome_language",
        )
        return tuple(n for n in names if getattr(self, n))


def later_years(text: str, commitment_year: int, max_event_year: int = MAX_EVENT_YEAR) -> list[int]:
    return sorted(
        {y for y in (int(m) for m in _YEAR.findall(text)) if commitment_year < y <= max_event_year}
    )


def diagnose(text: str | None, commitment_year: int | None) -> RetrospectiveFlags:
    body = text or ""
    later = bool(commitment_year is not None and later_years(body, commitment_year))
    return RetrospectiveFlags(
        later_year_mention=later,
        completion_language=bool(SIGNALS["completion_language"].search(body)),
        disbursement_language=bool(SIGNALS["disbursement_language"].search(body)),
        status_outcome_language=bool(SIGNALS["status_outcome_language"].search(body)),
        label_revealing_terms=bool(LABEL_REVEALING.search(body)),
    )
