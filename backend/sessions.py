"""Opaque refresh families, transactional rotation, and session-bound CSRF."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import uuid

from sqlalchemy import select, update

from backend.authentication import AuthenticationError
from backend.models import RefreshSession, User


COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/auth"


class CsrfError(Exception):
    pass


@dataclass
class SessionGrant:
    user_id: int
    family_id: uuid.UUID
    expires_at: datetime
    raw_token: str = field(repr=False)


def refresh_digest(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[A-Za-z0-9_-]{64}", raw):
        return None
    return hashlib.sha256(("student-marketplace:refresh:v1:" + raw).encode("ascii")).hexdigest()


def csrf_token(settings, user_id, family_id):
    payload = f"student-marketplace:csrf:v1:{user_id}:{family_id.hex}".encode("ascii")
    return hmac.new(settings.jwt_secret_key.get_secret_value().encode(), payload, hashlib.sha256).hexdigest()


def validate_origin(settings, origin, *, required=False):
    if (required and origin is None) or (origin is not None and origin not in settings.frontend_origins):
        raise CsrfError("Request origin or CSRF token is invalid")


def validate_csrf_header(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise CsrfError("Request origin or CSRF token is invalid")


def require_matching_csrf(settings, record, submitted):
    if not hmac.compare_digest(csrf_token(settings, record.user_id, record.family_id), submitted):
        raise CsrfError("Request origin or CSRF token is invalid")


def revoke_family(session, user_id, family_id, now):
    session.execute(update(RefreshSession).where(RefreshSession.user_id == user_id,
        RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now))


def revoke_user_sessions(session, user_id, now):
    """Reusable transactional helper for later password/deletion/admin workflows."""
    session.execute(select(User.id).where(User.id == user_id).with_for_update())
    session.execute(update(RefreshSession).where(RefreshSession.user_id == user_id,
        RefreshSession.revoked_at.is_(None)).values(revoked_at=now))


def new_login_session(database, user_id, settings, *, clock):
    with database.session() as session:
        user = session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None or not user.verified or user.suspended:
            raise AuthenticationError("Invalid credentials or account unavailable")
        now = clock()
        raw = secrets.token_urlsafe(48)
        family_id = uuid.uuid4()
        expires = now + timedelta(days=settings.refresh_session_days)
        session.add(RefreshSession(user_id=user.id, token_digest=refresh_digest(raw),
            family_id=family_id, created_at=now, expires_at=expires))
        return SessionGrant(user.id, family_id, expires, raw)


def rotate_refresh_session(database, raw, submitted_csrf, settings, *, clock):
    digest = refresh_digest(raw)
    if digest is None:
        return None
    with database.session() as session:
        initial = session.scalar(select(RefreshSession).where(RefreshSession.token_digest == digest))
        if initial is None:
            return None
        require_matching_csrf(settings, initial, submitted_csrf)
        user = session.scalar(select(User).where(User.id == initial.user_id).with_for_update())
        record = session.scalar(select(RefreshSession).where(RefreshSession.id == initial.id).with_for_update().execution_options(populate_existing=True))
        if user is None or record is None:
            return None
        now = clock()
        if record.successor_id is not None:
            revoke_family(session, user.id, record.family_id, now)
            return None  # Commit replay revocation before router returns 401.
        if not user.verified or user.suspended:
            revoke_user_sessions(session, user.id, now)
            return None
        if record.revoked_at is not None or record.expires_at <= now:
            return None
        successor_raw = secrets.token_urlsafe(48)
        successor = RefreshSession(user_id=user.id, token_digest=refresh_digest(successor_raw),
            family_id=record.family_id, predecessor_id=record.id,
            created_at=now, expires_at=record.expires_at)
        session.add(successor)
        session.flush()
        record.successor_id, record.revoked_at = successor.id, now
        return SessionGrant(user.id, record.family_id, record.expires_at, successor_raw)


def logout_session(database, raw, submitted_csrf, settings, *, clock):
    digest = refresh_digest(raw)
    if digest is None:
        return
    with database.session() as session:
        initial = session.scalar(select(RefreshSession).where(RefreshSession.token_digest == digest))
        if initial is None:
            return
        require_matching_csrf(settings, initial, submitted_csrf)
        session.execute(select(User.id).where(User.id == initial.user_id).with_for_update())
        revoke_family(session, initial.user_id, initial.family_id, clock())


def retrieve_csrf(database, raw, settings, *, clock):
    digest = refresh_digest(raw)
    if digest is None:
        return None
    with database.session() as session:
        record = session.scalar(select(RefreshSession).where(RefreshSession.token_digest == digest))
        if record is None or record.revoked_at is not None or record.expires_at <= clock():
            return None
        user = session.get(User, record.user_id)
        if user is None or not user.verified or user.suspended:
            return None
        return csrf_token(settings, user.id, record.family_id)


def set_refresh_cookie(response, grant, settings, now):
    response.set_cookie(COOKIE_NAME, grant.raw_token, path=COOKIE_PATH,
        httponly=True, samesite="lax", secure=settings.refresh_cookie_secure,
        max_age=max(0, int((grant.expires_at - now).total_seconds())),
        expires=grant.expires_at.astimezone(timezone.utc))


def clear_refresh_cookie(response, settings):
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True,
        samesite="lax", secure=settings.refresh_cookie_secure)
