"""Initial portable SQLite schema snapshot (independent revision stream)."""
from alembic import op

revision = "sqlite_0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = (
    r"""
CREATE TABLE categories (
	id SMALLINT NOT NULL, 
	"key" VARCHAR(32) NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_categories_fixed CHECK ((id=1 AND key='electronics' AND name='Electronics') OR (id=2 AND key='clothing' AND name='Clothing') OR (id=3 AND key='books' AND name='Books') OR (id=4 AND key='furniture' AND name='Furniture') OR (id=5 AND key='other' AND name='Other')), 
	UNIQUE ("key"), 
	UNIQUE (name), 
	CONSTRAINT ck_sqlite_categories_key_length CHECK (length(key) <= 32), 
	CONSTRAINT ck_sqlite_categories_name_length CHECK (length(name) <= 50)
)
""",
    r"""
CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(512) NOT NULL, 
	verified BOOLEAN DEFAULT false NOT NULL, 
	suspended BOOLEAN DEFAULT false NOT NULL, 
	role VARCHAR(16) DEFAULT 'student' NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	name VARCHAR(100), 
	avatar_path VARCHAR(1024), 
	phone VARCHAR(30), 
	telegram_username VARCHAR(32), 
	external_contact_url VARCHAR(2048), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_users_email CHECK (email = lower(trim(email)) AND email REGEXP '^[^\s@]+@sdu[.]edu[.]kz$'), 
	CONSTRAINT ck_users_role CHECK (role IN ('student', 'admin')), 
	CONSTRAINT ck_users_password_hash CHECK (length(trim(password_hash)) > 0), 
	UNIQUE (email), 
	CONSTRAINT ck_sqlite_users_email_length CHECK (length(email) <= 254), 
	CONSTRAINT ck_sqlite_users_password_hash_length CHECK (length(password_hash) <= 512), 
	CONSTRAINT ck_sqlite_users_verified_boolean CHECK (verified IN (0,1)), 
	CONSTRAINT ck_sqlite_users_suspended_boolean CHECK (suspended IN (0,1)), 
	CONSTRAINT ck_sqlite_users_role_length CHECK (length(role) <= 16), 
	CONSTRAINT ck_sqlite_users_name_length CHECK (length(name) <= 100), 
	CONSTRAINT ck_sqlite_users_avatar_path_length CHECK (length(avatar_path) <= 1024), 
	CONSTRAINT ck_sqlite_users_phone_length CHECK (length(phone) <= 30), 
	CONSTRAINT ck_sqlite_users_telegram_username_length CHECK (length(telegram_username) <= 32), 
	CONSTRAINT ck_sqlite_users_external_contact_url_length CHECK (length(external_contact_url) <= 2048)
)
""",
    r"""
CREATE TABLE email_codes (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	purpose VARCHAR(32) NOT NULL, 
	digest VARCHAR(128) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	expires_at DATETIME NOT NULL, 
	wrong_attempts INTEGER DEFAULT '0' NOT NULL, 
	consumed_at DATETIME, 
	invalidated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_email_codes_purpose CHECK (purpose IN ('registration', 'password_reset')), 
	CONSTRAINT ck_email_codes_attempts CHECK (wrong_attempts BETWEEN 0 AND 5), 
	CONSTRAINT ck_email_codes_digest CHECK (length(trim(digest)) > 0), 
	CONSTRAINT ck_email_codes_expiry CHECK (expires_at > created_at), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT ck_sqlite_email_codes_purpose_length CHECK (length(purpose) <= 32), 
	CONSTRAINT ck_sqlite_email_codes_digest_length CHECK (length(digest) <= 128)
)
""",
    r"""
CREATE INDEX ix_email_codes_user_purpose ON email_codes (user_id, purpose)
""",
    r"""
CREATE TABLE listings (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	category_id SMALLINT NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	description VARCHAR(2000) NOT NULL, 
	price INTEGER NOT NULL, 
	currency VARCHAR(3) DEFAULT 'KZT' NOT NULL, 
	condition VARCHAR(4) NOT NULL, 
	status VARCHAR(8) DEFAULT 'pending' NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	published_at DATETIME, 
	rejection_reason VARCHAR(300), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_listings_title CHECK (length(title) BETWEEN 3 AND 120 AND NOT (title REGEXP '^\s|\s$')), 
	CONSTRAINT ck_listings_description CHECK (length(description) BETWEEN 10 AND 2000), 
	CONSTRAINT ck_listings_price CHECK (typeof(price) = 'integer' AND price >= 0 AND price <= 100000000000), 
	CONSTRAINT ck_listings_currency CHECK (currency = 'KZT'), 
	CONSTRAINT ck_listings_condition CHECK (condition IN ('new','used')), 
	CONSTRAINT ck_listings_status CHECK (status IN ('pending','active','sold','rejected','removed')), 
	CONSTRAINT ck_listings_publication CHECK (status NOT IN ('active','sold') OR published_at IS NOT NULL), 
	CONSTRAINT ck_listings_pending_unpublished CHECK (status != 'pending' OR published_at IS NULL), 
	CONSTRAINT ck_listings_rejection CHECK (status != 'rejected' OR (rejection_reason IS NOT NULL AND length(rejection_reason) BETWEEN 1 AND 300 AND rejection_reason REGEXP '\S')), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_sqlite_listings_title_length CHECK (length(title) <= 120), 
	CONSTRAINT ck_sqlite_listings_description_length CHECK (length(description) <= 2000), 
	CONSTRAINT ck_sqlite_listings_currency_length CHECK (length(currency) <= 3), 
	CONSTRAINT ck_sqlite_listings_condition_length CHECK (length(condition) <= 4), 
	CONSTRAINT ck_sqlite_listings_status_length CHECK (length(status) <= 8), 
	CONSTRAINT ck_sqlite_listings_rejection_reason_length CHECK (length(rejection_reason) <= 300)
)
""",
    r"""
CREATE INDEX ix_listings_active_publication ON listings (published_at)
""",
    r"""
CREATE INDEX ix_listings_owner_status ON listings (owner_id, status)
""",
    r"""
CREATE TABLE refresh_sessions (
	id CHAR(32) DEFAULT (gen_random_uuid()) NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_digest VARCHAR(128) NOT NULL, 
	family_id CHAR(32) DEFAULT (gen_random_uuid()) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	predecessor_id CHAR(32), 
	successor_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_refresh_sessions_digest CHECK (length(trim(token_digest)) > 0), 
	CONSTRAINT ck_refresh_sessions_expiry CHECK (expires_at > created_at), 
	CONSTRAINT ck_refresh_sessions_predecessor CHECK (predecessor_id IS NULL OR predecessor_id <> id), 
	CONSTRAINT ck_refresh_sessions_successor CHECK (successor_id IS NULL OR successor_id <> id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (token_digest), 
	UNIQUE (predecessor_id), 
	FOREIGN KEY(predecessor_id) REFERENCES refresh_sessions (id) ON DELETE SET NULL, 
	UNIQUE (successor_id), 
	FOREIGN KEY(successor_id) REFERENCES refresh_sessions (id) ON DELETE SET NULL, 
	CONSTRAINT ck_sqlite_refresh_sessions_token_digest_length CHECK (length(token_digest) <= 128)
)
""",
    r"""
CREATE INDEX ix_refresh_sessions_user_family ON refresh_sessions (user_id, family_id)
""",
    r"""
CREATE TABLE listing_photos (
	id INTEGER NOT NULL, 
	listing_id INTEGER NOT NULL, 
	storage_path VARCHAR(1024) NOT NULL, 
	position SMALLINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_listing_photos_position CHECK (position BETWEEN 1 AND 5), 
	CONSTRAINT ck_listing_photos_path CHECK (storage_path REGEXP ('^listings/' || CAST(listing_id AS TEXT) || '/[0-9a-f]{32}[.](jpg|png|webp)$')), 
	CONSTRAINT uq_listing_photos_slot UNIQUE (listing_id, position), 
	FOREIGN KEY(listing_id) REFERENCES listings (id) ON DELETE CASCADE, 
	UNIQUE (storage_path), 
	CONSTRAINT ck_sqlite_listing_photos_storage_path_length CHECK (length(storage_path) <= 1024)
)
""",
    r"""
CREATE TABLE listing_reports (
	id INTEGER NOT NULL, 
	reporter_id INTEGER NOT NULL, 
	listing_id INTEGER NOT NULL, 
	reason VARCHAR(32) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	reviewed_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_listing_reports_reason CHECK (reason IN ('spam','prohibited_items','misleading_information')), 
	CONSTRAINT ck_listing_reports_review_time CHECK (reviewed_at IS NULL OR reviewed_at >= created_at), 
	FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(listing_id) REFERENCES listings (id) ON DELETE CASCADE, 
	CONSTRAINT ck_sqlite_listing_reports_reason_length CHECK (length(reason) <= 32)
)
""",
    r"""
CREATE INDEX ix_listing_reports_listing ON listing_reports (listing_id)
""",
    r"""
CREATE INDEX ix_listing_reports_reporter_listing ON listing_reports (reporter_id, listing_id)
""",
    r"""
CREATE INDEX ix_listing_reports_unreviewed ON listing_reports (created_at)
""",
)


def upgrade():
    for statement in DDL:
        op.execute(statement)
    # Idempotent by the fixed category primary key; no account/demo seeding.
    op.execute("INSERT INTO categories(id,key,name) VALUES (1,'electronics','Electronics') ON CONFLICT(id) DO NOTHING")
    op.execute("INSERT INTO categories(id,key,name) VALUES (2,'clothing','Clothing') ON CONFLICT(id) DO NOTHING")
    op.execute("INSERT INTO categories(id,key,name) VALUES (3,'books','Books') ON CONFLICT(id) DO NOTHING")
    op.execute("INSERT INTO categories(id,key,name) VALUES (4,'furniture','Furniture') ON CONFLICT(id) DO NOTHING")
    op.execute("INSERT INTO categories(id,key,name) VALUES (5,'other','Other') ON CONFLICT(id) DO NOTHING")


def downgrade():
    op.execute("DROP TABLE listing_reports")
    op.execute("DROP TABLE listing_photos")
    op.execute("DROP TABLE refresh_sessions")
    op.execute("DROP TABLE listings")
    op.execute("DROP TABLE email_codes")
    op.execute("DROP TABLE users")
    op.execute("DROP TABLE categories")
