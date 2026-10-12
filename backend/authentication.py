"""Password login and a shared guard based on current database eligibility."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from backend.models import User, RefreshSession
from backend.tokens import AccessTokenError, validate_access_token


class AuthenticationError(Exception):
    pass


def authenticate_student(database, email, password):
    with database.session() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None or not user.verified or user.suspended:
            raise AuthenticationError("Invalid credentials or account unavailable")
        try:
            PasswordHasher().verify(user.password_hash, password)
        except (VerificationError, InvalidHashError):
            raise AuthenticationError("Invalid credentials or account unavailable") from None
        return user


bearer = HTTPBearer(auto_error=False)


def authentication_required():
    return HTTPException(status_code=401, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})


def require_verified_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise authentication_required()
    try:
        user_id, family_id = validate_access_token(request.app.state.settings, credentials.credentials, clock=request.app.state.clock)
    except AccessTokenError:
        raise authentication_required() from None
    with request.app.state.database.session() as session:
        user = session.get(User, user_id)
        if user is None or not user.verified or user.suspended:
            raise authentication_required()
        active = session.scalar(select(RefreshSession.id).where(
            RefreshSession.user_id == user.id, RefreshSession.family_id == family_id,
            RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > request.app.state.clock(),
        ).limit(1))
        if active is None:
            raise authentication_required()
        return user
