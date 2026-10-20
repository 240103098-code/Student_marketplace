"""Explicit FILE SQLite migrations; deliberately separate from PostgreSQL."""
from alembic import context
from sqlalchemy.exc import SQLAlchemyError
from backend.config import load_settings
from backend.database import Base, Database
from backend import models

settings = context.config.attributes.get("settings") or load_settings()
url = settings.database_url.get_secret_value()
if not url.startswith("sqlite+pysqlite:") or url == "sqlite+pysqlite:///:memory:":
    raise RuntimeError("SQLite migration stream requires a persistent local SQLite file.")
if context.is_offline_mode():
    raise RuntimeError("Use online SQLite migrations so foreign keys and BEGIN IMMEDIATE are enforced.")
database = Database(settings)
try:
    with database.engine.begin() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata,
            transactional_ddl=True, version_table="alembic_version_sqlite")
        with context.begin_transaction():
            context.run_migrations()
except SQLAlchemyError:
    raise RuntimeError("SQLite migration failed; verify local file access, writer availability and migration state.") from None
finally:
    database.dispose()
