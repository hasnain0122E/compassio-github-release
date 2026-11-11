"""Parsing of the research paper's ``rio_marker`` climate label.

Definition source (authors' documentation, verified in Task 003):
Qi, J., Tang, Y., Zhang, Z., Wang, Y. & Qian, H. (2026). *A Benchmark Dataset of Chinese
Development Finance with Climate Relevance and SDG Annotations from 2000-2021.*
Scientific Data 13, 277. https://doi.org/10.1038/s41597-026-06605-9

* Table 1 column header: "Rio Marker (Overall, Mitigation, Adaptation)", with examples
  ``2,0,2`` (drought-resistant rice) and ``2,2,0`` (electric/hybrid vehicles).
* Methods, Data processing: scores 0 ("not targeted"), 1 ("significant objective"),
  2 ("principal objective").

These are the authors' annotated labels (multi-annotator, cross-checked with ClimateBERT per
the paper); they are not independently verified ground truth.

The relationship ``rio_overall == max(rio_mitigation, rio_adaptation)`` holds in every row of
the registered file but is *not documented* by the paper, so it is checked and reported
(``overall_is_max``), never assumed by the parser.
"""

from dataclasses import dataclass

VALID_SCORES = frozenset({0, 1, 2})
SCORE_MEANING = {0: "not targeted", 1: "significant objective", 2: "principal objective"}


@dataclass(frozen=True, slots=True)
class RioMarker:
    rio_overall: int
    rio_mitigation: int
    rio_adaptation: int

    @property
    def is_climate_related(self) -> bool:
        """Binary target: the authors scored the project significant or principal overall."""
        return self.rio_overall > 0

    @property
    def overall_is_max(self) -> bool:
        return self.rio_overall == max(self.rio_mitigation, self.rio_adaptation)


def parse_rio_marker(value: str | None) -> RioMarker | None:
    """Parse ``"overall,mitigation,adaptation"``.

    Returns ``None`` for a blank value; raises ``ValueError`` for anything that is not three
    comma-separated integers in {0, 1, 2}.
    """
    if value is None or value.strip() == "":
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"rio_marker must be three comma-separated integers: {value!r}")
    scores = [int(p) for p in parts]
    if any(s not in VALID_SCORES for s in scores):
        raise ValueError(f"rio_marker scores must be 0, 1 or 2: {value!r}")
    return RioMarker(rio_overall=scores[0], rio_mitigation=scores[1], rio_adaptation=scores[2])
