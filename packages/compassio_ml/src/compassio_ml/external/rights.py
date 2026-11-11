"""ML-use eligibility per source (``configs/ml_rights_eligibility_v2.yaml``).

Operational restrictions recorded from evidence; **not** legal clearance. A source that is
missing from the file is treated as restricted for every use (fail closed).
"""

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_RIGHTS_CONFIG = Path("configs") / "ml_rights_eligibility_v2.yaml"
RIGHTS_VERSION = "ml_rights_eligibility_v2.0"


class UseStatus(StrEnum):
    PERMITTED_PENDING_REVIEW = "permitted_pending_review"
    RESTRICTED = "restricted"
    NOT_APPLICABLE = "not_applicable"


class Use(StrEnum):
    TRAINING = "ml_training"
    EVALUATION = "automated_evaluation"
    HUMAN_REVIEW = "human_review_reference"


class SourceEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ml_training: UseStatus
    automated_evaluation: UseStatus
    human_review_reference: UseStatus
    evidence: str


class RightsEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    evidence_snapshot: str
    sources: dict[str, SourceEligibility]

    def status(self, source_id: str, use: Use) -> UseStatus:
        entry = self.sources.get(source_id)
        if entry is None:
            return UseStatus.RESTRICTED
        value: UseStatus = getattr(entry, use.value)
        return value

    def permitted(self, source_id: str, use: Use) -> bool:
        return self.status(source_id, use) == UseStatus.PERMITTED_PENDING_REVIEW

    def restricted_sources(self) -> frozenset[str]:
        """Sources restricted for BOTH training and automated evaluation."""
        return frozenset(
            s
            for s in self.sources
            if not self.permitted(s, Use.TRAINING) and not self.permitted(s, Use.EVALUATION)
        )


def load_rights(path: Path = DEFAULT_RIGHTS_CONFIG) -> RightsEligibility:
    with path.open(encoding="utf-8") as handle:
        data: Any = yaml.safe_load(handle)
    rights = RightsEligibility.model_validate(data)
    if rights.version != RIGHTS_VERSION:
        raise ValueError(f"expected rights version {RIGHTS_VERSION}, got {rights.version}")
    return rights
