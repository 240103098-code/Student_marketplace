"""One-time activation and cooldown-limited replacement, serialized per user."""

from datetime import timedelta
import hmac

from sqlalchemy import select

from backend.email_codes import code_digest, issue_email_code, utc_now
from backend.models import EmailCode, User


def verify_registration_code(database, email, raw_code, settings, *, clock=utc_now):
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or user.verified or user.suspended:
            return False
        record = session.scalar(select(EmailCode).where(
            EmailCode.user_id == user.id, EmailCode.purpose == "registration",
            EmailCode.consumed_at.is_(None), EmailCode.invalidated_at.is_(None),
            EmailCode.wrong_attempts < 5,
        ).order_by(EmailCode.created_at.desc(), EmailCode.id.desc()).limit(1).with_for_update())
        now = clock()
        if record is None or record.expires_at <= now:
            return False
        digest = code_digest(settings, user.id, "registration", raw_code)
        if not hmac.compare_digest(record.digest, digest):
            record.wrong_attempts += 1
            if record.wrong_attempts == 5:
                record.invalidated_at = now
            # Returning normally commits accounting before the router raises 400.
            return False
        user.verified = True
        record.consumed_at = now
        return True


def resend_registration_code(database, email, settings, sender, *, clock=utc_now):
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or user.verified or user.suspended:
            return False
        now = clock()
        latest = session.scalar(select(EmailCode.created_at).where(
            EmailCode.user_id == user.id, EmailCode.purpose == "registration",
        ).order_by(EmailCode.created_at.desc(), EmailCode.id.desc()).limit(1))
        if latest is not None and now - latest < timedelta(seconds=60):
            return False
        issue_email_code(session, user, "registration", settings, sender, now=now)
        return True
