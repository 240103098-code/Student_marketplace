"""Explicit PostgreSQL/volatile-memory engine and transaction helpers, without import side effects."""

import argparse
from contextlib import contextmanager, nullcontext
import threading
import re
import uuid

from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import ConfigurationError, Settings, load_settings


class Base(DeclarativeBase):
    """Shared metadata for models introduced by later tasks."""


class Database:
    def __init__(self, settings: Settings):
        url = make_url(settings.database_url.get_secret_value())
        self.is_memory = url.drivername == "sqlite+pysqlite" and url.database == ":memory:"
        self._guard = threading.Lock() if self.is_memory else nullcontext()
        self._disposed = False
        if self.is_memory:
            if settings.app_env == "production":
                raise ValueError("Memory storage is forbidden in production")
            self.engine = create_engine(url, poolclass=StaticPool,
                connect_args={"check_same_thread": False}, echo=False, hide_parameters=True)
            @event.listens_for(self.engine, "connect")
            def configure(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.create_function("regexp", 2,
                    lambda pattern, value: int(value is not None and re.search(pattern, value) is not None), deterministic=True)
                connection.create_function("gen_random_uuid", 0, lambda: uuid.uuid4().hex)
                # SQLAlchemy emulates ILIKE using lower(); SQLite defaults to ASCII.
                connection.create_function("lower", 1, lambda value: value.lower() if value is not None else None, deterministic=True)
        else:
            # Preserve PostgreSQL driver, bounded connectivity and native row locks.
            url = url.set(drivername="postgresql+psycopg")
            self.engine = create_engine(url, pool_pre_ping=True, echo=False,
                hide_parameters=True, connect_args={"connect_timeout": 3,
                "options": "-c statement_timeout=5000"})
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        if self.is_memory:
            # Explicit construction only: never performed while importing models.
            from backend.models import Category, CATEGORIES
            Base.metadata.create_all(self.engine)
            with self.session() as session:
                session.add_all(Category(id=id, key=key, name=name) for id,key,name in CATEGORIES)

    @contextmanager
    def session(self):
        # SQLite FOR UPDATE is ignored. The guard instead covers the entire
        # transaction, including reads, commit/rollback AND connection return.
        with self._guard:
            if self._disposed:
                raise RuntimeError("Database has been disposed")
            session = self.session_factory()
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise
            finally:
                session.close()

    def check_connection(self):
        with self._guard:
            if self._disposed:
                raise RuntimeError("Database has been disposed")
            with self.engine.connect() as connection:
                return connection.execute(text("SELECT 1")).scalar_one() == 1

    def dispose(self):
        with self._guard:
            self.engine.dispose()
            # PostgreSQL Engine.dispose() traditionally permits reconnection.
            # Only memory disposal is terminal: reconnecting would silently lose schema.
            self._disposed = self.is_memory


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check configured database connectivity")
    parser.add_argument("action", choices=["check"])
    parser.parse_args(argv)
    database = None
    try:
        database = Database(load_settings())
        if not database.check_connection():
            raise RuntimeError("Unexpected connection-check response")
    except ConfigurationError as error:
        print(f"Database connection check failed: {error}")
        return 1
    except (SQLAlchemyError, OSError, ValueError, RuntimeError):
        # Never interpolate driver exceptions or URLs containing credentials.
        print("Database connection check failed; verify database configuration and availability.")
        return 1
    finally:
        if database is not None:
            database.dispose()
    print("Database connection check succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
