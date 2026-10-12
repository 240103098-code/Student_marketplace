"""Persist an unverified student and send their purpose-scoped verification code."""

from argon2 import PasswordHasher, Type
from sqlalchemy.exc import IntegrityError

from backend.models import User
from backend.email_codes import issue_email_code, utc_now


class DuplicateEmailError(Exception):
    pass


def register_student(database, email, password, settings, sender, *, clock=utc_now):
    password_hash = PasswordHasher(type=Type.ID).hash(password)
    try:
        with database.session() as session:
            user = User(email=email, password_hash=password_hash)
            session.add(user)
            session.flush()
            issue_email_code(session, user, "registration", settings, sender, now=clock())
        return user
    except IntegrityError as error:
        details = getattr(error.orig, "diag", None)
        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(details, "constraint_name", None) == "users_email_key"
        ):
            raise DuplicateEmailError("University email is already registered") from None
        raise
