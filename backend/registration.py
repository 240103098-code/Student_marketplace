"""Persist a new unverified student; activation and email are later workflows."""

from argon2 import PasswordHasher, Type
from sqlalchemy.exc import IntegrityError

from backend.models import User


class DuplicateEmailError(Exception):
    pass


def register_student(database, email, password):
    password_hash = PasswordHasher(type=Type.ID).hash(password)
    try:
        with database.session() as session:
            user = User(email=email, password_hash=password_hash)
            session.add(user)
            session.flush()
        return user
    except IntegrityError as error:
        details = getattr(error.orig, "diag", None)
        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(details, "constraint_name", None) == "users_email_key"
        ):
            raise DuplicateEmailError("University email is already registered") from None
        raise
