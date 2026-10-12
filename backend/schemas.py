"""Strict registration inputs and deliberately limited public responses."""

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from typing import Literal


class UniversityEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: str = Field(strict=True, max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def validate_university_email(cls, value):
        if not isinstance(value, str):
            raise ValueError("Email must be a string")
        trimmed = value.strip()
        domain = trimmed.rpartition("@")[2]
        if not domain.isascii() or domain.lower() != "sdu.edu.kz":
            raise ValueError("Email must use the university domain")
        normalized = trimmed.lower()
        try:
            validated = validate_email(normalized, check_deliverability=False, allow_smtputf8=False)
        except EmailNotValidError:
            raise ValueError("Email is malformed") from None
        if validated.domain != "sdu.edu.kz":
            raise ValueError("Email must use the university domain")
        return validated.normalized


class RegistrationRequest(UniversityEmailRequest):
    password: SecretStr = Field(strict=True, min_length=12, max_length=128)


class LoginRequest(RegistrationRequest):
    pass


class AccessTokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class VerifyEmailRequest(UniversityEmailRequest):
    code: SecretStr = Field(strict=True, min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def validate_ascii_code(cls, value):
        if not all("0" <= digit <= "9" for digit in value.get_secret_value()):
            raise ValueError("Code must contain six ASCII digits")
        return value


class ResendVerificationRequest(UniversityEmailRequest):
    pass


class RegistrationResponse(BaseModel):
    id: int
    email: str
    verified: bool


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    current_password: SecretStr = Field(strict=True, min_length=12, max_length=128)
    new_password: SecretStr = Field(strict=True, min_length=12, max_length=128)


class ForgotPasswordRequest(UniversityEmailRequest):
    pass


class ResetPasswordRequest(VerifyEmailRequest):
    new_password: SecretStr = Field(strict=True, min_length=12, max_length=128)
