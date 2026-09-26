"""Authorization foundation — organisation membership enforcement.

Development may accept X-Organisation-Id / X-User-Id headers when
auth_dev_fallback is True. Production must not treat headers as identity.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from config.settings import get_settings
from core.errors import AuthenticationError, AuthorizationError
from database.models import Membership, Organisation, User
from schemas.common import new_id


def ensure_org_user(
    session: Session,
    organisation_id: str,
    user_id: str,
    *,
    email: Optional[str] = None,
    role: str = "member",
) -> tuple:
    """Ensure org + user + membership exist (dev bootstrap). Returns (org, user, membership)."""
    org = session.get(Organisation, organisation_id)
    if not org:
        org = Organisation(id=organisation_id, name=organisation_id)
        session.add(org)
        session.flush()
    user = session.get(User, user_id)
    if not user:
        user = User(
            id=user_id,
            organisation_id=organisation_id,
            email=email or f"{user_id}@local.dev",
            hashed_password="!",  # not used for header auth
            role=role,
        )
        session.add(user)
        session.flush()
    membership = (
        session.query(Membership)
        .filter_by(organisation_id=organisation_id, user_id=user_id)
        .one_or_none()
    )
    if not membership:
        membership = Membership(
            id=new_id("MEMB-"),
            organisation_id=organisation_id,
            user_id=user_id,
            role=role,
        )
        session.add(membership)
        session.flush()
    return org, user, membership


def assert_membership(
    session: Session,
    organisation_id: str,
    user_id: str,
) -> Membership:
    membership = (
        session.query(Membership)
        .filter_by(organisation_id=organisation_id, user_id=user_id, status="active")
        .one_or_none()
    )
    if membership:
        return membership
    settings = get_settings()
    # Dev fallback: auto-create membership only in development
    if getattr(settings, "auth_dev_fallback", True) and getattr(settings, "environment", "development") in (
        "development",
        "test",
    ):
        _, _, membership = ensure_org_user(session, organisation_id, user_id)
        return membership
    raise AuthorizationError(
        f"User {user_id} is not a member of organisation {organisation_id}"
    )


def resolve_identity(
    *,
    organisation_id: Optional[str],
    user_id: Optional[str],
    session: Optional[Session] = None,
) -> dict:
    """Resolve request identity. Headers alone are not proof in production."""
    settings = get_settings()
    env = getattr(settings, "environment", "development")
    org = organisation_id or "default-org"
    uid = user_id or "default-user"
    if env not in ("development", "test") and not getattr(settings, "auth_dev_fallback", False):
        if not organisation_id or not user_id:
            raise AuthenticationError("Authenticated identity required")
    if session is not None:
        assert_membership(session, org, uid)
    return {"organisation_id": org, "user_id": uid}
