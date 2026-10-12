from contextlib import nullcontext

import pytest
from fastapi import Depends, FastAPI


def original_service():
    return "original"


def previous_fake():
    return "previous"


def current_fake():
    return "fake"


def make_example_app():
    """Keep this demonstration route out of the production application."""
    application = FastAPI()

    @application.get("/example")
    def example(value: str = Depends(original_service)):
        return {"value": value}

    return application


@pytest.mark.parametrize("has_previous_override", [False, True])
@pytest.mark.parametrize("raise_in_test", [False, True])
def test_client_restores_overrides_and_closes(
    client_factory, has_previous_override, raise_in_test
):
    application = make_example_app()
    if has_previous_override:
        application.dependency_overrides[original_service] = previous_fake
    previous_overrides = application.dependency_overrides.copy()
    expected_value = "previous" if has_previous_override else "original"
    outcome = (
        pytest.raises(RuntimeError, match="test exception")
        if raise_in_test
        else nullcontext()
    )

    with outcome:
        with client_factory(application) as first_client:
            assert first_client.get("/example").json() == {"value": expected_value}
            application.dependency_overrides[original_service] = current_fake
            assert first_client.get("/example").json() == {"value": "fake"}
            if raise_in_test:
                raise RuntimeError("test exception")

    assert first_client.is_closed
    assert application.dependency_overrides == previous_overrides
    with client_factory(application) as fresh_client:
        assert fresh_client.get("/example").json() == {"value": expected_value}
    assert fresh_client.is_closed
    assert application.dependency_overrides == previous_overrides
