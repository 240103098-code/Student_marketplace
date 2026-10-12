"""Own-avatar persistence, with post-commit cleanup reported honestly."""

from sqlalchemy import select

from backend.authentication import AuthenticationError
from backend.images import ImageStorage, ImageStorageError, canonical_image
from backend.models import RefreshSession, User
from backend.tokens import AccessTokenError, validate_access_token


def locked_avatar_user(session, user_id, token, settings, clock):
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    try:
        token_user_id, family = validate_access_token(settings, token, clock=clock)
    except AccessTokenError:
        raise AuthenticationError('Authentication required') from None
    if user is None or token_user_id != user_id or not user.verified or user.suspended:
        raise AuthenticationError('Authentication required')
    active = session.scalar(select(RefreshSession.id).where(RefreshSession.user_id == user_id,
        RefreshSession.family_id == family, RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > clock()).limit(1))
    if active is None:
        raise AuthenticationError('Authentication required')
    return user


def mutate_avatar(database, user_id, token, settings, *, raw=None, clock):
    image = None if raw is None else canonical_image(raw)
    storage = ImageStorage(settings.upload_dir)
    created = previous = None
    try:
        with database.session() as session:
            user = locked_avatar_user(session, user_id, token, settings, clock)
            previous = user.avatar_path
            if previous is not None:
                storage.path(previous, user_id)  # Never replace/remove an unsafe stored path.
            created = None if image is None else storage.write(image, user_id)
            user.avatar_path = created
            session.flush()
    except BaseException:
        if created is not None:
            try: storage.delete(created, user_id)
            except ImageStorageError: pass  # Document potential orphan; never remove prior image.
        raise
    cleanup_pending = False
    if previous is not None:
        try: storage.delete(previous, user_id)
        except ImageStorageError: cleanup_pending = True
    return cleanup_pending


def read_avatar(database, user_id, token, settings, *, clock):
    with database.session() as session:
        user = locked_avatar_user(session, user_id, token, settings, clock)
        if user.avatar_path is None:
            return None
        return ImageStorage(settings.upload_dir).read(user.avatar_path, user_id)
