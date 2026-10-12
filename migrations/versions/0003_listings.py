"""Fixed categories and manual-moderation listing/photo/report representation."""

from alembic import op

revision = '0003_listings'
down_revision = '0002_accounts'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE categories (
            id SMALLINT PRIMARY KEY,
            key VARCHAR(32) NOT NULL UNIQUE,
            name VARCHAR(50) NOT NULL UNIQUE,
            CONSTRAINT ck_categories_fixed CHECK ((id,key,name) IN
                ((1,'electronics','Electronics'),(2,'clothing','Clothing'),
                 (3,'books','Books'),(4,'furniture','Furniture'),(5,'other','Other')))
        )
    """)
    op.execute("""INSERT INTO categories(id,key,name) VALUES
        (1,'electronics','Electronics'),(2,'clothing','Clothing'),(3,'books','Books'),
        (4,'furniture','Furniture'),(5,'other','Other')""")
    op.execute("""
        CREATE TABLE listings (
            id BIGSERIAL PRIMARY KEY,
            owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category_id SMALLINT NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
            title VARCHAR(120) NOT NULL,
            description VARCHAR(2000) NOT NULL,
            price NUMERIC(12,2) NOT NULL,
            currency VARCHAR(3) NOT NULL DEFAULT 'KZT',
            condition VARCHAR(4) NOT NULL,
            status VARCHAR(8) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            published_at TIMESTAMPTZ,
            rejection_reason VARCHAR(300),
            CONSTRAINT ck_listings_title CHECK (length(title) BETWEEN 3 AND 120 AND title !~ '^[[:space:]]|[[:space:]]$'),
            CONSTRAINT ck_listings_description CHECK (length(description) BETWEEN 10 AND 2000),
            CONSTRAINT ck_listings_price CHECK (price >= 0 AND price <= 1000000000),
            CONSTRAINT ck_listings_currency CHECK (currency = 'KZT'),
            CONSTRAINT ck_listings_condition CHECK (condition IN ('new','used')),
            CONSTRAINT ck_listings_status CHECK (status IN ('pending','active','sold','rejected','removed')),
            CONSTRAINT ck_listings_publication CHECK (status NOT IN ('active','sold') OR published_at IS NOT NULL),
            CONSTRAINT ck_listings_pending_unpublished CHECK (status != 'pending' OR published_at IS NULL),
            CONSTRAINT ck_listings_rejection CHECK (status != 'rejected' OR (rejection_reason IS NOT NULL AND length(rejection_reason) BETWEEN 1 AND 300 AND rejection_reason ~ '[^[:space:]]'))
        )
    """)
    op.create_index('ix_listings_owner_status','listings',['owner_id','status'])
    op.execute("CREATE INDEX ix_listings_active_publication ON listings(published_at) WHERE status = 'active'")
    op.execute("""
        CREATE TABLE listing_photos (
            id BIGSERIAL PRIMARY KEY,
            listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            storage_path VARCHAR(1024) NOT NULL UNIQUE,
            position SMALLINT NOT NULL,
            CONSTRAINT ck_listing_photos_position CHECK (position BETWEEN 1 AND 5),
            CONSTRAINT ck_listing_photos_path CHECK (storage_path ~ ('^listings/' || listing_id::text || '/[0-9a-f]{32}[.](jpg|png|webp)$')),
            CONSTRAINT uq_listing_photos_slot UNIQUE(listing_id,position)
        )
    """)
    op.execute("""
        CREATE TABLE listing_reports (
            id BIGSERIAL PRIMARY KEY,
            reporter_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            reason VARCHAR(32) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reviewed_at TIMESTAMPTZ,
            CONSTRAINT ck_listing_reports_reason CHECK (reason IN ('spam','prohibited_items','misleading_information')),
            CONSTRAINT ck_listing_reports_review_time CHECK (reviewed_at IS NULL OR reviewed_at >= created_at)
        )
    """)
    op.create_index('ix_listing_reports_reporter_listing','listing_reports',['reporter_id','listing_id'])
    op.create_index('ix_listing_reports_listing','listing_reports',['listing_id'])
    op.execute('CREATE INDEX ix_listing_reports_unreviewed ON listing_reports(created_at) WHERE reviewed_at IS NULL')


def downgrade():
    op.drop_table('listing_reports')
    op.drop_table('listing_photos')
    op.drop_table('listings')
    op.drop_table('categories')
