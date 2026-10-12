import base64
from datetime import datetime, timedelta, timezone
import json
import unittest
import uuid

import jwt

from backend.config import load_settings
from backend.tokens import AccessTokenError, AUDIENCE, ISSUER, issue_access_token, validate_access_token


class AccessTokenTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
        self.settings = load_settings(environ={"DATABASE_URL": "postgresql://test_user@localhost/test_database", "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40}, env_file=None)
        self.key = self.settings.jwt_secret_key.get_secret_value()
        self.family = uuid.UUID(hex="b" * 32)
        self.claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "123", "type": "access", "iat": int(self.now.timestamp()), "exp": int(self.now.timestamp()) + 900, "jti": "a" * 32, "sid": self.family.hex}

    def validate(self, token):
        return validate_access_token(self.settings, token, clock=lambda: self.now)

    def encoded(self, claims=None, **kwargs):
        return jwt.encode(self.claims if claims is None else claims, self.key, algorithm=kwargs.pop("algorithm", "HS256"), **kwargs)

    def test_issued_claims_and_exact_expiry_boundary(self):
        token = issue_access_token(self.settings, 123, self.family, clock=lambda: self.now)
        claims = jwt.decode(token, options={"verify_signature": False})
        self.assertEqual(set(claims), set(self.claims))
        self.assertEqual(claims["exp"] - claims["iat"], 900)
        self.assertEqual(claims["iss"], ISSUER)
        self.assertEqual(claims["aud"], AUDIENCE)
        self.assertEqual(self.validate(token), (123, self.family))
        self.now += timedelta(seconds=900) - timedelta(microseconds=1)
        self.assertEqual(self.validate(token), (123, self.family))
        self.now += timedelta(microseconds=1)
        with self.assertRaises(AccessTokenError):
            self.validate(token)

    def test_signatures_algorithms_malformed_and_missing_algorithm_fail_safely(self):
        header = base64.urlsafe_b64encode(b"{}").rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(json.dumps(self.claims).encode()).rstrip(b"=").decode()
        tokens = ["SENSITIVE_TOKEN_MARKER", "", "a" * 4097, None,
            jwt.encode(self.claims, "SYNTHETIC_WRONG_KEY_" + "z" * 40, algorithm="HS256"),
            self.encoded(algorithm="HS384"), jwt.encode(self.claims, "", algorithm="none"), f"{header}.{payload}.signature"]
        for index, token in enumerate(tokens):
            with self.subTest(case=index), self.assertRaises(AccessTokenError) as error:
                self.validate(token)
            self.assertEqual(str(error.exception), "Access token is invalid or expired")

    def test_every_required_claim_must_be_present(self):
        for name in self.claims:
            claims = self.claims.copy()
            del claims[name]
            with self.subTest(claim=name), self.assertRaises(AccessTokenError):
                self.validate(self.encoded(claims))

    def test_wrong_claim_values_types_and_extra_sensitive_claims_fail(self):
        mutations = [{"iss": "other"}, {"aud": "other"}, {"aud": [AUDIENCE]},
            {"type": "refresh"}, {"sub": 123}, {"sub": "-1"}, {"sub": "0"},
            {"sub": "001"}, {"sub": "1.5"}, {"sub": str(2**63)}, {"sub": "１２３"},
            {"iat": True}, {"exp": "99999999999"}, {"jti": ""}, {"jti": 1},
            {"password": "SENSITIVE_CLAIM_MARKER"}, {"exp": self.claims["exp"] + 3600}, {"sid": ""}, {"sid": 1}]
        for index, mutation in enumerate(mutations):
            with self.subTest(case=index), self.assertRaises(AccessTokenError):
                self.validate(self.encoded(self.claims | mutation))

    def test_expired_and_future_issued_tokens_fail(self):
        expired = self.claims | {"iat": self.claims["iat"] - 900, "exp": self.claims["iat"]}
        future = self.claims | {"iat": self.claims["iat"] + 1, "exp": self.claims["exp"] + 1}
        for claims in (expired, future):
            with self.assertRaises(AccessTokenError):
                self.validate(self.encoded(claims))
