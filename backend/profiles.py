"""Own-profile mutation rechecks authorization under the account lock."""

from sqlalchemy import select

from backend.authentication import AuthenticationError
from backend.models import RefreshSession, User
from backend.tokens import AccessTokenError, validate_access_token


def update_own_profile(database, user_id, access_token, changes, settings, *, clock):
    with database.session() as session:
        user = session.scalar(select(User).where(User.id == user_id).with_for_update())
        try:
            token_user_id, family_id = validate_access_token(settings, access_token, clock=clock)
        except AccessTokenError:
            raise AuthenticationError('Authentication required') from None
        if user is None or user.id != token_user_id or not user.verified or user.suspended:
            raise AuthenticationError('Authentication required')
        active = session.scalar(select(RefreshSession.id).where(
            RefreshSession.user_id == user.id, RefreshSession.family_id == family_id,
            RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > clock(),
        ).limit(1))
        if active is None:
            raise AuthenticationError('Authentication required')
        for name, value in changes.model_dump(exclude_unset=True).items():
            setattr(user, name, value)
        session.flush()
        return user
