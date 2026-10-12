"""Alembic loads settings explicitly when a migration command is executed."""

from alembic import context
from sqlalchemy.exc import SQLAlchemyError

from backend.config import load_settings
from backend.database import Base, Database
from backend import models  # Register metadata only; no settings or connections.


settings = context.config.attributes.get("settings")
if settings is None:
    settings = load_settings()
database = Database(settings)
try:
    if context.is_offline_mode():
        context.configure(
            url=database.engine.url,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
except SQLAlchemyError:
    raise RuntimeError("PostgreSQL migration failed; verify database availability and migration state.") from None
finally:
    database.dispose()
