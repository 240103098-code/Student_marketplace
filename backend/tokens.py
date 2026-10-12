"""Strict, short-lived access JWTs with explicit settings and UTC clock."""

import re
import uuid

import jwt

from backend.email_codes import utc_now


ISSUER = "student-marketplace"
AUDIENCE = "student-marketplace-students"
REQUIRED_CLAIMS = {"iss", "aud", "sub", "type", "iat", "exp", "jti", "sid"}


class AccessTokenError(Exception):
    pass


def issue_access_token(settings, user_id, family_id, *, clock=utc_now):
    issued_at = int(clock().timestamp())
    duration = settings.jwt_access_minutes * 60
    claims = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": str(user_id), "type": "access",
        "iat": issued_at, "exp": issued_at + duration, "jti": uuid.uuid4().hex,
        "sid": family_id.hex,
    }
    return jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")


def validate_access_token(settings, token, *, clock=utc_now):
    try:
        if not isinstance(token, str) or len(token) > 4096:
            raise AccessTokenError()
        claims = jwt.decode(
            token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"],
            issuer=ISSUER, audience=AUDIENCE,
            options={"require": sorted(REQUIRED_CLAIMS), "strict_aud": True,
                "verify_exp": False, "verify_iat": False},
        )
        # Manual time checks use the same explicitly injected clock as issuance;
        # all signature/issuer/audience checks remain enabled in the JWT library.
        if set(claims) != REQUIRED_CLAIMS or claims["type"] != "access":
            raise AccessTokenError()
        if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
            raise AccessTokenError()
        now = clock().timestamp()
        if claims["iat"] > now or claims["exp"] <= now:
            raise AccessTokenError()
        if claims["exp"] - claims["iat"] != settings.jwt_access_minutes * 60:
            raise AccessTokenError()
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
            raise AccessTokenError()
        user_id = int(subject)
        if not 0 < user_id < 2**63 or str(user_id) != subject:
            raise AccessTokenError()
        if not isinstance(claims["jti"], str) or not re.fullmatch(r"[0-9a-f]{32}", claims["jti"]):
            raise AccessTokenError()
        if not isinstance(claims["sid"], str) or not re.fullmatch(r"[0-9a-f]{32}", claims["sid"]):
            raise AccessTokenError()
        return user_id, uuid.UUID(hex=claims["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError, AccessTokenError):
        raise AccessTokenError("Access token is invalid or expired") from None
