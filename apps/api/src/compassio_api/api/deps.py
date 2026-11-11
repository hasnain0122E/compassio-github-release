"""Shared request dependencies: database session and the source-rights access policy."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from compassio_api.core.config import Settings, get_settings
from compassio_api.services.access import AccessPolicy, resolve_policy


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_policy(request: Request, session: SessionDep, settings: SettingsDep) -> AccessPolicy:
    """Policy for metadata routes (``/sources``): never fails for missing rights."""
    event = getattr(request.app.state, "event_authorization", None)
    return resolve_policy(session, settings.effective_source_access, event)


def require_data_access(policy: Annotated[AccessPolicy, Depends(get_policy)]) -> AccessPolicy:
    """Policy for source-derived data routes: 403 when no source may be served."""
    policy.require_any()
    return policy


PolicyDep = Annotated[AccessPolicy, Depends(get_policy)]
DataPolicyDep = Annotated[AccessPolicy, Depends(require_data_access)]
