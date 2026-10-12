"""Non-enumerating recovery requests and one-time password resets."""

from datetime import timedelta
import hmac

from argon2 import PasswordHasher
from sqlalchemy import select

from backend.email_codes import code_digest, issue_email_code, utc_now
from backend.models import EmailCode, User
from backend.sessions import revoke_user_sessions


def request_password_reset(database, email, settings, sender, *, clock=utc_now):
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or not user.verified or user.suspended:
            return
        now = clock()
        latest = session.scalar(select(EmailCode.created_at).where(
            EmailCode.user_id == user.id, EmailCode.purpose == 'password_reset',
        ).order_by(EmailCode.created_at.desc(), EmailCode.id.desc()).limit(1))
        if latest is not None and now - latest < timedelta(seconds=60):
            return
        issue_email_code(session, user, 'password_reset', settings, sender, now=now)


def reset_student_password(database, email, raw_code, new_password, settings, *, clock=utc_now):
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or not user.verified or user.suspended:
            return False
        record = session.scalar(select(EmailCode).where(
            EmailCode.user_id == user.id, EmailCode.purpose == 'password_reset',
            EmailCode.consumed_at.is_(None), EmailCode.invalidated_at.is_(None),
            EmailCode.wrong_attempts < 5,
        ).order_by(EmailCode.created_at.desc(), EmailCode.id.desc()).limit(1).with_for_update())
        now = clock()
        if record is None or record.expires_at <= now:
            return False
        digest = code_digest(settings, user.id, 'password_reset', raw_code)
        if not hmac.compare_digest(record.digest, digest):
            record.wrong_attempts += 1
            if record.wrong_attempts == 5:
                record.invalidated_at = now
            return False  # Commit attempts before the router returns an error.
        record.consumed_at = now
        user.password_hash = PasswordHasher().hash(new_password)
        revoke_user_sessions(session, user.id, now)
        return True
