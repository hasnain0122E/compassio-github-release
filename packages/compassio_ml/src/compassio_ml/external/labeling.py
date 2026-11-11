"""Human labelling workflow (label policy ``rio_label_policy_v2.1``).

* Reviewer worksheets are **blind**: text and provenance only; never a source climate
  indicator (donor marker, GCF theme, World Bank theme) or a model output.
* Reviewer columns are created empty. Nothing in this package fills them; no AI-generated or
  automatically derived value is ever written into a reviewer or final-label column.
* Every ``reviewer_id`` must be registered in ``reviewers.yaml`` (git-ignored) as a genuine
  person with a role; placeholder IDs (``example*``) are refused.
* External-test items need reviewers A and B (different people) and, where they disagree, flag
  the item or declare insufficient information, a third-person adjudicator.
* Only frozen, adjudicated items count as verified. Sealed external-test labels are readable
  only via :func:`open_sealed_labels`, which requires a frozen v2 evaluation plan.
"""

import csv
import hashlib
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

LABEL_POLICY_VERSION = "rio_label_policy_v2.1"
CONFIDENCE = ("low", "medium", "high")
ROLES = ("reviewer_a", "reviewer_b", "adjudicator", "auditor")

WORKSHEET_CONTEXT_COLUMNS = [
    "item_id",
    "worksheet",
    "source_id",
    "publisher",
    "source_project_id",
    "document_url",
    "document_version",
    "text_date",
    "text_timing",
    "country_iso3",
    "title",
    "description",
]
REVIEWER_COLUMNS = [
    "reviewer_id",
    "rio_mitigation",
    "rio_adaptation",
    "rio_overall",
    "confidence",
    "insufficient_information",
    "evidence_quote",
    "rationale",
    "flag_needs_discussion",
    "reviewed_at",
]
WORKSHEET_COLUMNS = WORKSHEET_CONTEXT_COLUMNS + REVIEWER_COLUMNS
# Shown to the adjudicator only after both independent labels exist.
ADJUDICATION_CONTEXT_COLUMNS = [
    "donor_rio_mitigation",
    "donor_rio_adaptation",
    "gcf_theme",
    "wb_climate_themes",
    "sector_family",
]
ADJUDICATOR_COLUMNS = [
    "adjudicator_id",
    "final_rio_mitigation",
    "final_rio_adaptation",
    "final_status",
    "adjudication_rationale",
]
FINAL_STATUSES = ("verified", "needs_review")
_SPACE = re.compile(r"\s+")


class SealedTestAccessError(PermissionError):
    """External-test labels were requested without a frozen v2 evaluation plan."""


class ReviewWorkflowError(RuntimeError):
    """A review step was attempted before its preconditions were met."""


# ------------------------------------------------------------------ reviewers
class Reviewer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")
    is_human: Literal[True]
    roles: list[str] = Field(min_length=1)
    attestation: str = Field(min_length=20)
    conflicts_of_interest: str = ""

    @field_validator("reviewer_id")
    @classmethod
    def _not_placeholder(cls, value: str) -> str:
        if value.lower().startswith("example"):
            raise ValueError("placeholder reviewer_id; register a genuine person's pseudonym")
        return value

    @field_validator("roles")
    @classmethod
    def _roles(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(ROLES)
        if unknown:
            raise ValueError(f"unknown roles {sorted(unknown)}; allowed {ROLES}")
        return value


class ReviewerRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewers: list[Reviewer]

    @model_validator(mode="after")
    def _unique(self) -> "ReviewerRegistry":
        ids = [r.reviewer_id for r in self.reviewers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate reviewer_id")
        return self

    def has_role(self, reviewer_id: str, role: str) -> bool:
        return any(r.reviewer_id == reviewer_id and role in r.roles for r in self.reviewers)


def load_reviewers(path: Path) -> ReviewerRegistry:
    if not path.is_file():
        raise ReviewWorkflowError(
            f"No reviewer registry at {path}. Copy reviewers.template.yaml to reviewers.yaml "
            "and register each genuine reviewer (pseudonymous IDs are fine)."
        )
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ReviewerRegistry.model_validate(data)


REVIEWERS_TEMPLATE = """\
# Copy to reviewers.yaml (git-ignored) and replace the placeholder entries with GENUINE people.
# reviewer_id may be a pseudonym, but each must belong to one real person. IDs starting with
# "example" are refused by the validator. Roles: reviewer_a, reviewer_b, adjudicator, auditor.
# A person may hold several roles, but A, B and the adjudicator of an item must differ.
reviewers:
  - reviewer_id: example_reviewer_a
    is_human: true
    roles: [reviewer_a]
    attestation: "I am a human reviewer and will label independently without AI assistance."
    conflicts_of_interest: "e.g. also develops v2 models (must be disclosed)"
"""


# ------------------------------------------------------------------ reviewer rows
class ReviewerLabel(BaseModel):
    """One completed reviewer row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    reviewer_id: str = Field(min_length=1)
    rio_mitigation: int | None = Field(default=None, ge=0, le=2)
    rio_adaptation: int | None = Field(default=None, ge=0, le=2)
    rio_overall: int | None = Field(default=None, ge=0, le=2)
    confidence: str
    insufficient_information: bool = False
    evidence_quote: str = ""
    rationale: str = Field(min_length=10)
    flag_needs_discussion: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> "ReviewerLabel":
        if self.confidence not in CONFIDENCE:
            raise ValueError(f"confidence must be one of {CONFIDENCE}")
        scores = (self.rio_mitigation, self.rio_adaptation, self.rio_overall)
        if self.insufficient_information:
            if any(s is not None for s in scores):
                raise ValueError("insufficient_information rows must leave the Rio values blank")
            return self
        if any(s is None for s in scores):
            raise ValueError("rio_mitigation, rio_adaptation and rio_overall are required")
        assert self.rio_mitigation is not None and self.rio_adaptation is not None
        if self.rio_overall != max(self.rio_mitigation, self.rio_adaptation):
            raise ValueError("rio_overall must equal max(rio_mitigation, rio_adaptation)")
        if not self.evidence_quote.strip():
            raise ValueError("evidence_quote is required (verbatim phrase from title/description)")
        return self

    @property
    def scores(self) -> tuple[int | None, int | None]:
        return self.rio_mitigation, self.rio_adaptation


def item_id(worksheet: str, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{worksheet}:{candidate_id}".encode()).hexdigest()
    return f"itm_{digest[:16]}"


def text_fingerprint(title: str | None, description: str | None) -> str:
    joined = f"{title or ''}\n{description or ''}"
    return hashlib.sha256(_SPACE.sub(" ", joined).strip().encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    return _SPACE.sub(" ", text).strip().lower()


def build_worksheet(items: pd.DataFrame, worksheet: str) -> pd.DataFrame:
    """Blind reviewer worksheet: context columns + empty reviewer columns."""
    frame = pd.DataFrame(
        {
            "item_id": [item_id(worksheet, c) for c in items["candidate_id"]],
            "worksheet": worksheet,
            "source_id": items["source_id"].to_numpy(),
            "publisher": items["publisher"].to_numpy(),
            "source_project_id": items["source_record_id"].to_numpy(),
            "document_url": items["document_url"].to_numpy(),
            "document_version": (
                items["retrieval_id"] + ":" + items["raw_file_sha256"].str[:16]
            ).to_numpy(),
            "text_date": items["text_date"].to_numpy(),
            "text_timing": items["text_timing"].to_numpy(),
            "country_iso3": items["country_iso3"].to_numpy(),
            "title": items["title_clean"].to_numpy(),
            "description": items["description_clean"].to_numpy(),
        }
    )
    for column in REVIEWER_COLUMNS:
        frame[column] = ""
    leaked = set(frame.columns) & set(ADJUDICATION_CONTEXT_COLUMNS)
    if leaked:
        raise AssertionError(f"source labels leaked into reviewer worksheet: {leaked}")
    return frame


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        frame.to_csv(handle, index=False, quoting=csv.QUOTE_ALL)


def read_sheet(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


# ------------------------------------------------------------------ validation
@dataclass
class ReviewValidation:
    valid: list[ReviewerLabel] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    blank_rows: int = 0
    total_rows: int = 0

    @property
    def complete(self) -> bool:
        return not self.errors and self.blank_rows == 0 and len(self.valid) == self.total_rows


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "y")


def _int(value: str) -> int | None:
    value = value.strip()
    return None if value == "" else int(value)


def validate_completed(
    path: Path,
    *,
    expected: pd.DataFrame,
    registry: ReviewerRegistry,
    role: str,
) -> ReviewValidation:
    """Validate a returned worksheet against the issued one (``expected``: the blank sheet).

    Checks columns, item IDs, unchanged text, registered reviewer with ``role``, value rules
    and that ``evidence_quote`` occurs verbatim (whitespace/case-insensitive) in the text."""
    result = ReviewValidation()
    frame = read_sheet(path)
    missing = [c for c in WORKSHEET_COLUMNS if c not in frame.columns]
    if missing:
        result.errors.append(f"{path.name}: missing columns {missing}")
        return result
    issued = expected.set_index("item_id")
    result.total_rows = len(issued)
    if frame["item_id"].duplicated().any():
        result.errors.append(f"{path.name}: duplicate item_id rows")
    unknown = set(frame["item_id"]) - set(issued.index)
    if unknown:
        result.errors.append(f"{path.name}: {len(unknown)} unknown item_id values")
    absent = set(issued.index) - set(frame["item_id"])
    if absent:
        result.errors.append(f"{path.name}: {len(absent)} issued items missing")
    for line, row in enumerate(frame.to_dict("records"), start=2):
        iid = row["item_id"]
        if iid not in issued.index:
            continue
        ref = issued.loc[iid]
        if text_fingerprint(row["title"], row["description"]) != text_fingerprint(
            ref["title"], ref["description"]
        ):
            result.errors.append(f"{path.name}:{line}: title/description was edited")
            continue
        filled = [c for c in REVIEWER_COLUMNS if c not in ("flag_needs_discussion",)]
        if not any(str(row[c]).strip() for c in filled):
            result.blank_rows += 1
            continue
        reviewer = row["reviewer_id"].strip()
        if not registry.has_role(reviewer, role):
            result.errors.append(
                f"{path.name}:{line}: reviewer_id {reviewer!r} not registered with role {role}"
            )
            continue
        try:
            label = ReviewerLabel(
                item_id=iid,
                reviewer_id=reviewer,
                rio_mitigation=_int(row["rio_mitigation"]),
                rio_adaptation=_int(row["rio_adaptation"]),
                rio_overall=_int(row["rio_overall"]),
                confidence=row["confidence"].strip().lower(),
                insufficient_information=_bool(row["insufficient_information"]),
                evidence_quote=row["evidence_quote"],
                rationale=row["rationale"],
                flag_needs_discussion=_bool(row["flag_needs_discussion"]),
            )
        except (ValueError, ValidationError) as exc:
            result.errors.append(f"{path.name}:{line}: {exc}")
            continue
        quote = _norm(label.evidence_quote)
        if quote and quote not in _norm(f"{ref['title']} {ref['description']}"):
            result.errors.append(f"{path.name}:{line}: evidence_quote not found verbatim in text")
            continue
        result.valid.append(label)
    reviewers = {label.reviewer_id for label in result.valid}
    if len(reviewers) > 1:
        result.errors.append(f"{path.name}: several reviewer_ids in one worksheet: {reviewers}")
    return result


def cohen_kappa(a: Sequence[int], b: Sequence[int]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if expected == 1.0:
        return None
    return (observed - expected) / (1 - expected)


def agreement(first: list[ReviewerLabel], second: list[ReviewerLabel]) -> dict[str, object]:
    """Agreement over items both reviewers scored (insufficient-information rows excluded)."""
    a = {x.item_id: x for x in first}
    b = {x.item_id: x for x in second}
    if {x.reviewer_id for x in first} & {x.reviewer_id for x in second}:
        raise ValueError("the same reviewer_id appears in both worksheets")
    both = sorted(set(a) & set(b))
    scored = [
        i for i in both if not a[i].insufficient_information and not b[i].insufficient_information
    ]
    out: dict[str, object] = {
        "items_double_reviewed": len(both),
        "items_both_scored": len(scored),
        "items_with_insufficient_information": len(both) - len(scored),
    }
    for name in ("rio_mitigation", "rio_adaptation", "rio_overall"):
        xa = [int(getattr(a[i], name)) for i in scored]
        xb = [int(getattr(b[i], name)) for i in scored]
        out[f"{name}_percent_agreement"] = (
            sum(p == q for p, q in zip(xa, xb, strict=True)) / len(scored) if scored else None
        )
        out[f"{name}_cohen_kappa"] = cohen_kappa(xa, xb)
    out["binary_climate_related_cohen_kappa"] = cohen_kappa(
        [int((a[i].rio_overall or 0) > 0) for i in scored],
        [int((b[i].rio_overall or 0) > 0) for i in scored],
    )
    out["disagreements"] = [i for i in scored if a[i].scores != b[i].scores]
    return out


# ------------------------------------------------------------------ master records
class LabelRecord(BaseModel):
    """Master record of the human-reviewable dataset (one per item)."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    source_id: str
    publisher: str
    source_project_id: str
    document_url: str | None
    description_sha256: str | None
    document_date: str | None
    document_version: str
    proposed_rio_mitigation: int | None = None
    proposed_rio_adaptation: int | None = None
    proposed_label_origin: str = "none"
    label_evidence: str = ""
    reviewer_a: ReviewerLabel | None = None
    reviewer_b: ReviewerLabel | None = None
    disagreement_status: str = "pending_review"
    adjudicated_by: str | None = None
    adjudication_rationale: str | None = None
    final_rio_mitigation: int | None = Field(default=None, ge=0, le=2)
    final_rio_adaptation: int | None = Field(default=None, ge=0, le=2)
    final_label_status: str = "unverified"
    label_policy_version: str = LABEL_POLICY_VERSION
    split_eligibility: str
    rights_status: str = "not_reviewed"

    @model_validator(mode="after")
    def _final_requires_humans(self) -> "LabelRecord":
        has_final = self.final_rio_mitigation is not None or self.final_rio_adaptation is not None
        if self.final_label_status == "verified" and (
            self.final_rio_mitigation is None or self.final_rio_adaptation is None
        ):
            raise ValueError("a verified item needs final Rio values")
        if (
            self.adjudicated_by
            and self.reviewer_a
            and self.reviewer_b
            and self.adjudicated_by in (self.reviewer_a.reviewer_id, self.reviewer_b.reviewer_id)
        ):
            raise ValueError("the adjudicator must be a third person")
        if has_final:
            if self.final_label_status != "verified":
                raise ValueError("final Rio values are only allowed on verified items")
            if self.reviewer_a is None or self.reviewer_b is None:
                raise ValueError("a final label requires two completed human reviews")
            if self.reviewer_a.reviewer_id == self.reviewer_b.reviewer_id:
                raise ValueError("reviewers A and B must be different people")
            if self.disagreement_status != "agree" and not self.adjudicated_by:
                raise ValueError("a disagreement needs a named adjudicator")
        return self


def open_sealed_labels(
    sealed_dir: Path, plan_sha256: str | None, frozen_plan_hash_file: Path
) -> pd.DataFrame:
    """Return sealed external-test labels only if a frozen v2 plan matches ``plan_sha256``."""
    if plan_sha256 is None or not frozen_plan_hash_file.is_file():
        raise SealedTestAccessError(
            "External-test labels are sealed until a v2 final evaluation plan is frozen "
            f"({frozen_plan_hash_file} does not exist or no plan hash was given)."
        )
    expected = frozen_plan_hash_file.read_text(encoding="utf-8").split()[0]
    if expected != plan_sha256:
        raise SealedTestAccessError("plan hash does not match the frozen v2 plan")
    path = sealed_dir / "external_test_labels.parquet"
    if not path.is_file():
        raise SealedTestAccessError(f"No adjudicated external-test labels at {path}")
    return pd.read_parquet(path)
