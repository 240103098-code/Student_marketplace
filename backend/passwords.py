"""Self-service password changes and all-session revocation are atomic."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select

from backend.authentication import AuthenticationError
from backend.models import RefreshSession, User
from backend.sessions import revoke_user_sessions
from backend.tokens import AccessTokenError, validate_access_token


class WrongCurrentPassword(Exception):
    pass


def change_student_password(database, user_id, access_token, current_password, new_password, settings, *, clock):
    with database.session() as session:
        user = session.scalar(select(User).where(User.id == user_id).with_for_update())
        # Recheck after the lock: a guard checked before waiting may have become stale.
        try:
            token_user_id, family_id = validate_access_token(settings, access_token, clock=clock)
        except AccessTokenError:
            raise AuthenticationError("Authentication required") from None
        now = clock()
        if user is None or user.id != token_user_id or not user.verified or user.suspended:
            raise AuthenticationError("Authentication required")
        active = session.scalar(select(RefreshSession.id).where(
            RefreshSession.user_id == user.id, RefreshSession.family_id == family_id,
            RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > now,
        ).limit(1))
        if active is None:
            raise AuthenticationError("Authentication required")
        try:
            PasswordHasher().verify(user.password_hash, current_password)
        except (VerificationError, InvalidHashError):
            raise WrongCurrentPassword() from None
        user.password_hash = PasswordHasher().hash(new_password)
        revoke_user_sessions(session, user.id, now)
