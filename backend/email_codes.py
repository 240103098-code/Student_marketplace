"""Transactional purpose-scoped issuance shared by verification services."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from sqlalchemy import select, update

from backend.models import EmailCode, User
from backend.mail import EmailDeliveryError


def code_digest(settings, user_id, purpose, code):
    # A domain-separated key/message prevents registration/reset and user reuse.
    key = settings.jwt_secret_key.get_secret_value().encode("utf-8")
    payload = f"student-marketplace:email-code:v1:{user_id}:{purpose}:{code}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


def issue_email_code(session, user, purpose, settings, sender, *, now=None):
    if purpose not in {"registration", "password_reset"}:
        raise ValueError("Unsupported email-code purpose")
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    now = utc_now() if now is None else now
    prior_digests = set(session.scalars(select(EmailCode.digest).where(
        EmailCode.user_id == user.id, EmailCode.purpose == purpose,
        EmailCode.consumed_at.is_(None),
    )))
    # A replacement must not accidentally resurrect an older unconsumed value.
    for _ in range(16):
        raw_code = f"{secrets.randbelow(1_000_000):06d}"
        digest = code_digest(settings, user.id, purpose, raw_code)
        if digest not in prior_digests:
            break
    else:
        raise EmailDeliveryError("Verification code issuance is temporarily unavailable")
    session.execute(update(EmailCode).where(
        EmailCode.user_id == user.id, EmailCode.purpose == purpose,
        EmailCode.consumed_at.is_(None), EmailCode.invalidated_at.is_(None),
        EmailCode.expires_at > now,
        EmailCode.wrong_attempts < 5,
    ).values(invalidated_at=now))
    record = EmailCode(user_id=user.id, purpose=purpose,
        digest=digest,
        created_at=now, expires_at=now + timedelta(minutes=10), wrong_attempts=0)
    session.add(record)
    session.flush()
    sender.send_code(user.email, raw_code, purpose)
    return record
