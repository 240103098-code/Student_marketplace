from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@contextmanager
def isolated_client(application):
    """Use overrides inside this context; prior overrides are restored on exit."""
    original_overrides = application.dependency_overrides.copy()
    test_client = TestClient(application)
    try:
        with test_client:
            yield test_client
    finally:
        try:
            test_client.close()
        finally:
            application.dependency_overrides.clear()
            application.dependency_overrides.update(original_overrides)


@pytest.fixture
def client_factory():
    """Create scoped clients for test-only apps with the same teardown rules."""
    return isolated_client


@pytest.fixture
def client(client_factory):
    """Reuse for endpoint tests; set app.dependency_overrides for fake services."""
    with client_factory(app) as test_client:
        yield test_client
