"""Account and marketplace representations; importing models never connects to a DB."""

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, Numeric, SmallInteger, UniqueConstraint, func, text
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


CATEGORIES = ((1, 'electronics', 'Electronics'), (2, 'clothing', 'Clothing'),
              (3, 'books', 'Books'), (4, 'furniture', 'Furniture'), (5, 'other', 'Other'))


class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (CheckConstraint("(id, key, name) IN ((1,'electronics','Electronics'), (2,'clothing','Clothing'), (3,'books','Books'), (4,'furniture','Furniture'), (5,'other','Other'))", name='ck_categories_fixed'),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class Listing(Base):
    __tablename__ = 'listings'
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 3 AND 120 AND title !~ '^[[:space:]]|[[:space:]]$'", name='ck_listings_title'),
        CheckConstraint('length(description) BETWEEN 10 AND 2000', name='ck_listings_description'),
        CheckConstraint('price >= 0 AND price <= 1000000000', name='ck_listings_price'),
        CheckConstraint("currency = 'KZT'", name='ck_listings_currency'),
        CheckConstraint("condition IN ('new','used')", name='ck_listings_condition'),
        CheckConstraint("status IN ('pending','active','sold','rejected','removed')", name='ck_listings_status'),
        CheckConstraint("status NOT IN ('active','sold') OR published_at IS NOT NULL", name='ck_listings_publication'),
        CheckConstraint("status != 'pending' OR published_at IS NULL", name='ck_listings_pending_unpublished'),
        CheckConstraint("status != 'rejected' OR (rejection_reason IS NOT NULL AND length(rejection_reason) BETWEEN 1 AND 300 AND rejection_reason ~ '[^[:space:]]')", name='ck_listings_rejection'),
        Index('ix_listings_owner_status', 'owner_id', 'status'),
        Index('ix_listings_active_publication', 'published_at', postgresql_where=text("status = 'active'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id', ondelete='RESTRICT'), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12,2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default='KZT', server_default='KZT', nullable=False)
    condition: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(8), default='pending', server_default='pending', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(300))

    @validates('title')
    def trim_title(self, key, value):
        return value.strip() if isinstance(value,str) else value


class ListingPhoto(Base):
    __tablename__ = 'listing_photos'
    __table_args__ = (
        CheckConstraint('position BETWEEN 1 AND 5', name='ck_listing_photos_position'),
        CheckConstraint("storage_path ~ ('^listings/' || listing_id::text || '/[0-9a-f]{32}[.](jpg|png|webp)$')", name='ck_listing_photos_path'),
        UniqueConstraint('listing_id', 'position', name='uq_listing_photos_slot'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey('listings.id', ondelete='CASCADE'), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class ListingReport(Base):
    __tablename__ = 'listing_reports'
    __table_args__ = (
        CheckConstraint("reason IN ('spam','prohibited_items','misleading_information')", name='ck_listing_reports_reason'),
        CheckConstraint('reviewed_at IS NULL OR reviewed_at >= created_at', name='ck_listing_reports_review_time'),
        Index('ix_listing_reports_reporter_listing', 'reporter_id', 'listing_id'),
        Index('ix_listing_reports_listing', 'listing_id'),
        Index('ix_listing_reports_unreviewed', 'created_at', postgresql_where=text('reviewed_at IS NULL')),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey('listings.id', ondelete='CASCADE'), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
