"""Shared, explicit disposable-database safeguards for PostgreSQL tests."""

import os
import unittest

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from backend.config import load_settings
from backend.database import Database


def open_disposable_database():
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        raise unittest.SkipTest("Set dedicated TEST_DATABASE_URL and matching TEST_DATABASE_CONFIRM to run real PostgreSQL tests")
    url = make_url(raw_url)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg"}
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not url.database
        or not url.database.startswith("student_marketplace_test_")
        or os.environ.get("TEST_DATABASE_CONFIRM") != url.database
    ):
        raise ValueError("Integration tests require an explicitly confirmed disposable loopback PostgreSQL test database")
    environment = {
        "APP_ENV": "test", "DATABASE_URL": raw_url,
        "JWT_SECRET_KEY": "TEST_ONLY_MARKER_" + "x" * 40,
    }
    settings = load_settings(environ=environment, env_file=None)
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            if connection.execute(text("SELECT current_database()")).scalar_one() != url.database:
                raise ValueError("Connected database does not match the disposable test database")
            if set(inspect(connection).get_table_names()) - {"alembic_version"}:
                raise ValueError("Disposable test database must contain no application tables")
    except BaseException:
        database.dispose()
        raise
    return settings, database, environment
