"""Public own-profile shapes and strict, partial profile edits."""

import ipaddress
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    verified: bool
    name: str | None
    phone: str | None
    telegram_username: str | None
    external_contact_url: str | None


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)

    name: str | None = Field(default=None, strict=True, max_length=100)
    phone: str | None = Field(default=None, strict=True, max_length=30)
    telegram_username: str | None = Field(default=None, strict=True, max_length=32)
    external_contact_url: str | None = Field(default=None, strict=True, max_length=2048)

    @field_validator('name', mode='before')
    @classmethod
    def name_nonblank(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Name must be a nonblank string')
        return value.strip()

    @field_validator('phone')
    @classmethod
    def phone_format(cls, value):
        if value is not None and not re.fullmatch(r'\+[0-9]{7,15}', value):
            raise ValueError('Phone must use international format')
        return value

    @field_validator('telegram_username')
    @classmethod
    def telegram_format(cls, value):
        if value is not None and not re.fullmatch(r'[A-Za-z0-9_]{5,32}', value):
            raise ValueError('Telegram username is invalid')
        return value

    @field_validator('external_contact_url')
    @classmethod
    def external_url_format(cls, value):
        if value is None:
            return None
        if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError('Contact URL is invalid')
        try:
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError()
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError()
            hostname = parsed.hostname
            try:
                ipaddress.ip_address(hostname)
            except ValueError:
                ascii_hostname = hostname.encode('idna').decode('ascii').rstrip('.')
                if len(ascii_hostname) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in ascii_hostname.split('.')):
                    raise ValueError()
        except (ValueError, UnicodeError):
            raise ValueError('Contact URL is invalid') from None
        return value

    @model_validator(mode='after')
    def nonempty_patch(self):
        if not self.model_fields_set:
            raise ValueError('Provide at least one profile field')
        return self
