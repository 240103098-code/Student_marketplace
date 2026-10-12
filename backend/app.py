"""Application creation is explicit and supports isolated injected dependencies."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.config import Settings
from backend.database import Database
from backend.mail import SmtpSender
from backend.email_codes import utc_now
from backend.routers.auth import router


def create_app(settings: Settings, database: Database | None = None, *, sender=None, clock=None):
    owns_database = database is None
    database = Database(settings) if database is None else database

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            if owns_database:
                database.dispose()

    app = FastAPI(title="Student Marketplace", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.email_sender = SmtpSender(settings) if sender is None else sender
    app.state.clock = utc_now if clock is None else clock

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # FastAPI's default error includes raw inputs; never return those.
        detail = "Invalid registration request." if request.url.path == "/auth/register" else "Invalid verification request."
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        detail = "Registration is temporarily unavailable." if request.url.path == "/auth/register" else "Verification is temporarily unavailable."
        return JSONResponse(status_code=500, content={"detail": detail})

    app.include_router(router)
    return app
