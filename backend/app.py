"""Application creation is explicit and supports isolated injected dependencies."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.config import Settings
from backend.database import Database
from backend.mail import SmtpSender
from backend.routers.auth import router


def create_app(settings: Settings, database: Database | None = None, *, sender=None):
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

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # FastAPI's default error includes raw inputs; never return those.
        return JSONResponse(status_code=422, content={"detail": "Invalid registration request."})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        return JSONResponse(status_code=500, content={"detail": "Registration is temporarily unavailable."})

    app.include_router(router)
    return app
