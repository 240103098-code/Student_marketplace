"""Accounts, purpose-scoped code digests, and refresh-session lineage."""

from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("suspended", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("role", sa.String(16), server_default="student", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("avatar_path", sa.String(1024)),
        sa.Column("phone", sa.String(30)),
        sa.Column("telegram_username", sa.String(32)),
        sa.Column("external_contact_url", sa.String(2048)),
        sa.CheckConstraint("email = lower(btrim(email)) AND email ~ '^[^[:space:]@]+@sdu[.]edu[.]kz$'", name="ck_users_email"),
        sa.CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("length(btrim(password_hash)) > 0", name="ck_users_password_hash"),
    )
    op.create_table(
        "email_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wrong_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("purpose IN ('registration', 'password_reset')", name="ck_email_codes_purpose"),
        sa.CheckConstraint("wrong_attempts BETWEEN 0 AND 5", name="ck_email_codes_attempts"),
        sa.CheckConstraint("length(btrim(digest)) > 0", name="ck_email_codes_digest"),
        sa.CheckConstraint("expires_at > created_at", name="ck_email_codes_expiry"),
    )
    op.create_index("ix_email_codes_user_purpose", "email_codes", ["user_id", "purpose"])
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_digest", sa.String(128), unique=True, nullable=False),
        sa.Column("family_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("predecessor_id", sa.Uuid(), sa.ForeignKey("refresh_sessions.id", ondelete="SET NULL"), unique=True),
        sa.Column("successor_id", sa.Uuid(), sa.ForeignKey("refresh_sessions.id", ondelete="SET NULL"), unique=True),
        sa.CheckConstraint("length(btrim(token_digest)) > 0", name="ck_refresh_sessions_digest"),
        sa.CheckConstraint("expires_at > created_at", name="ck_refresh_sessions_expiry"),
        sa.CheckConstraint("predecessor_id IS NULL OR predecessor_id <> id", name="ck_refresh_sessions_predecessor"),
        sa.CheckConstraint("successor_id IS NULL OR successor_id <> id", name="ck_refresh_sessions_successor"),
    )
    op.create_index("ix_refresh_sessions_user_family", "refresh_sessions", ["user_id", "family_id"])


def downgrade():
    op.drop_table("refresh_sessions")
    op.drop_table("email_codes")
    op.drop_table("users")
