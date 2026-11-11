"""Source-rights access policy (docs/security/source_rights_access_policy.md).

* ``local_development``: every registered source may be inspected on the developer's machine.
* ``public``: only sources whose ``rights_status`` is ``permitted`` or
  ``permitted_with_conditions`` (which the manifest model accepts only *with* written evidence)
  are served. Today that is **none**, so public data routes fail closed with HTTP 403.
* ``hackathon_event`` (Task 009): only the sources named by the configured event
  authorization (``services.event_access``), and only while its date window (if set) holds.
  Loopback clients only (enforced in ``main``). A user-reported organizer authorization, never
  a licence clearance.
* ``environment=production`` always uses ``public`` (see ``Settings.effective_source_access``).

Rights are read from the ``sources`` table, which ingestion copies from the committed manifest;
nothing in the API can change them.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from compassio_api.core.config import AccessMode
from compassio_api.db.models import Source
from compassio_api.services.event_access import EventAuthorization

PERMITTED_RIGHTS = frozenset({"permitted", "permitted_with_conditions"})

LOCAL_NOTICE = (
    "LOCAL DEVELOPMENT ONLY: source rights are not reviewed. Do not expose, screenshot for "
    "publication, or redistribute these records."
)
PUBLIC_NOTICE = "Only sources with an evidenced rights clearance are served."


def event_notice(event: EventAuthorization) -> str:
    return (
        f"EVENT DEMONSTRATION ONLY ({event.event}): served under an organizer authorization "
        f"reported by the team ({event.evidence_status}); not a licence clearance. Every source "
        "keeps rights_status not_reviewed. Local judging only: no public deployment, "
        "redistribution or commercial use. Show the source attribution."
    )


def event_inactive_notice(event: EventAuthorization | None) -> str:
    window = event.window if event is not None else "no authorization loaded"
    return f"Event authorization not active today (window: {window}); no source data is served."


class SourceRightsNotClearedError(Exception):
    """No source (or not the requested source) may be served in the current access mode."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    mode: AccessMode
    visible_source_ids: frozenset[str]
    notice: str

    def require_any(self) -> None:
        if not self.visible_source_ids:
            raise SourceRightsNotClearedError(
                "No source has an evidenced rights clearance, so source-derived records are "
                "not available in public mode. Local inspection requires "
                "COMPASSIO_SOURCE_DATA_ACCESS=local_development (or an active hackathon_event "
                "authorization) outside production."
            )

    def allows(self, source_id: str) -> bool:
        return source_id in self.visible_source_ids


def resolve_policy(
    session: Session,
    mode: AccessMode,
    event: EventAuthorization | None = None,
    today: date | None = None,
) -> AccessPolicy:
    # restricted_internal sources (e.g. unverified provenance) are never served, in any mode.
    rows = session.execute(
        select(Source.source_id, Source.rights_status).where(
            Source.access_tier != "restricted_internal"
        )
    ).all()
    if mode == "local_development":
        return AccessPolicy(mode, frozenset(s for s, _ in rows), LOCAL_NOTICE)
    if mode == "hackathon_event":
        if event is None or not event.active_on(today or date.today()):
            return AccessPolicy(mode, frozenset(), event_inactive_notice(event))
        allowed = set(event.sources)
        return AccessPolicy(
            mode, frozenset(s for s, _ in rows if s in allowed), event_notice(event)
        )
    visible = frozenset(s for s, status in rows if status in PERMITTED_RIGHTS)
    return AccessPolicy(mode, visible, PUBLIC_NOTICE)
