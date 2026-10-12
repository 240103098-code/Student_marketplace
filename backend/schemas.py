"""Strict registration inputs and deliberately limited public responses."""

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: str = Field(strict=True, max_length=254)
    password: SecretStr = Field(strict=True, min_length=12, max_length=128)

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


class RegistrationResponse(BaseModel):
    id: int
    email: str
    verified: bool
