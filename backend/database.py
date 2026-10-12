"""Explicit PostgreSQL engine and transaction helpers, without import side effects."""

import argparse
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import ConfigurationError, Settings, load_settings


class Base(DeclarativeBase):
    """Shared metadata for models introduced by later tasks."""


class Database:
    def __init__(self, settings: Settings):
        url = make_url(settings.database_url.get_secret_value())
        # Plain postgresql URLs must also use the explicitly installed psycopg.
        url = url.set(drivername="postgresql+psycopg")
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            echo=False,
            hide_parameters=True,
            connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
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
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1

    def dispose(self):
        self.engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check configured PostgreSQL connectivity")
    parser.add_argument("action", choices=["check"])
    parser.parse_args(argv)
    database = None
    try:
        database = Database(load_settings())
        if not database.check_connection():
            raise RuntimeError("Unexpected connection-check response")
    except ConfigurationError as error:
        print(f"PostgreSQL connection check failed: {error}")
        return 1
    except (SQLAlchemyError, OSError, ValueError, RuntimeError):
        # Never interpolate driver exceptions or URLs containing credentials.
        print("PostgreSQL connection check failed; verify database configuration and availability.")
        return 1
    finally:
        if database is not None:
            database.dispose()
    print("PostgreSQL connection check succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
