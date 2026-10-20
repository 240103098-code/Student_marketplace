"""SQLite-only storage adaptations; PostgreSQL model DDL stays native."""
from datetime import timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, Integer
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTC timestamps require timezone-aware input")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class MoneyCents(TypeDecorator):
    """Integer cents avoid SQLite floating-point NUMERIC coercion entirely."""
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, (bool, float)):
            raise ValueError("Money requires exact decimal input")
        amount = Decimal(value)
        if not amount.is_finite() or not 0 <= amount <= Decimal("1000000000") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Money requires bounded exact cents")
        return int(amount * 100)

    def process_result_value(self, value, dialect):
        return (Decimal(value) / 100).quantize(Decimal("0.01")) if value is not None else None


# These replacements execute only while compiling SQLite CREATE TABLE. The
# original named PostgreSQL checks and published Alembic revisions are unchanged.
SQLITE_CHECKS = {
    "ck_categories_fixed": "(id=1 AND key='electronics' AND name='Electronics') OR (id=2 AND key='clothing' AND name='Clothing') OR (id=3 AND key='books' AND name='Books') OR (id=4 AND key='furniture' AND name='Furniture') OR (id=5 AND key='other' AND name='Other')",
    "ck_users_email": r"email = lower(trim(email)) AND email REGEXP '^[^\s@]+@sdu[.]edu[.]kz$'",
    "ck_users_password_hash": "length(trim(password_hash)) > 0",
    "ck_email_codes_digest": "length(trim(digest)) > 0",
    "ck_refresh_sessions_digest": "length(trim(token_digest)) > 0",
    "ck_listings_title": r"length(title) BETWEEN 3 AND 120 AND NOT (title REGEXP '^\s|\s$')",
    "ck_listings_price": "typeof(price) = 'integer' AND price >= 0 AND price <= 100000000000",
    "ck_listings_rejection": r"status != 'rejected' OR (rejection_reason IS NOT NULL AND length(rejection_reason) BETWEEN 1 AND 300 AND rejection_reason REGEXP '\S')",
    "ck_listing_photos_path": r"storage_path REGEXP ('^listings/' || CAST(listing_id AS TEXT) || '/[0-9a-f]{32}[.](jpg|png|webp)$')",
}


@compiles(CheckConstraint, "sqlite")
def sqlite_check(constraint, compiler, **kw):
    replacement = SQLITE_CHECKS.get(constraint.name)
    if replacement is not None:
        constraint = CheckConstraint(replacement, name=constraint.name)
    return compiler.visit_check_constraint(constraint, **kw)
