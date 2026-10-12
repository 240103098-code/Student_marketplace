"""Account data representations only; importing models never connects to a DB."""

from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from backend.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email)) AND email ~ '^[^[:space:]@]+@sdu[.]edu[.]kz$'", name="ck_users_email"),
        CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),
        CheckConstraint("length(btrim(password_hash)) > 0", name="ck_users_password_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="student", server_default="student", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    avatar_path: Mapped[str | None] = mapped_column(String(1024))
    phone: Mapped[str | None] = mapped_column(String(30))
    telegram_username: Mapped[str | None] = mapped_column(String(32))
    external_contact_url: Mapped[str | None] = mapped_column(String(2048))

    @validates("email")
    def normalize_email(self, key, value):
        return value.strip().lower()

    def __repr__(self):
        return f"User(id={self.id!r})"


class EmailCode(Base):
    __tablename__ = "email_codes"
    __table_args__ = (
        CheckConstraint("purpose IN ('registration', 'password_reset')", name="ck_email_codes_purpose"),
        CheckConstraint("wrong_attempts BETWEEN 0 AND 5", name="ck_email_codes_attempts"),
        CheckConstraint("length(btrim(digest)) > 0", name="ck_email_codes_digest"),
        CheckConstraint("expires_at > created_at", name="ck_email_codes_expiry"),
        Index("ix_email_codes_user_purpose", "user_id", "purpose"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    digest: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wrong_attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"EmailCode(id={self.id!r}, purpose={self.purpose!r})"


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (
        CheckConstraint("length(btrim(token_digest)) > 0", name="ck_refresh_sessions_digest"),
        CheckConstraint("expires_at > created_at", name="ck_refresh_sessions_expiry"),
        CheckConstraint("predecessor_id IS NULL OR predecessor_id <> id", name="ck_refresh_sessions_predecessor"),
        CheckConstraint("successor_id IS NULL OR successor_id <> id", name="ck_refresh_sessions_successor"),
        Index("ix_refresh_sessions_user_family", "user_id", "family_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refresh_sessions.id", ondelete="SET NULL"), unique=True)
    successor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refresh_sessions.id", ondelete="SET NULL"), unique=True)

    def __repr__(self):
        return f"RefreshSession(id={self.id!r}, family_id={self.family_id!r})"
