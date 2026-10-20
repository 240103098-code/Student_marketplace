"""Application creation is explicit and supports isolated injected dependencies."""

from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.routers.admin import router as admin_router
from backend.config import Settings
from backend.database import Database
from backend.mail import SmtpSender
from backend.email_codes import utc_now
from backend.routers.auth import router
from backend.routers.users import router as users_router
from backend.routers.listings import router as listings_router
from backend.routers.listing_photos import router as listing_photos_router
from backend.sessions import CsrfError
from backend.images import ImageInputError, ImageStorageError


def create_app(settings: Settings, database: Database | None = None, *, sender=None, clock=None, limiter=None):
    owns_database = database is None
    database = Database(settings) if database is None else database
    owned_uploads = None
    if owns_database and database.is_memory:
        # Caller UPLOAD_DIR is never touched: volatile records own fresh images.
        owned_uploads = TemporaryDirectory(prefix="student-marketplace-memory-")
        settings = settings.model_copy(update={"upload_dir": Path(owned_uploads.name)})

    def close_owned_resources():
        if owns_database:
            database.dispose()
        if owned_uploads is not None:
            owned_uploads.cleanup()

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            close_owned_resources()

    app = FastAPI(title="Student Marketplace", lifespan=lifespan)
    app.state.close_owned_resources = close_owned_resources
    app.state.settings = settings
    app.state.database = database
    app.state.email_sender = SmtpSender(settings) if sender is None else sender
    app.state.clock = utc_now if clock is None else clock
    from backend.abuse import Limiter
    from backend.security_boundary import SecurityBoundary
    app.state.limiter=Limiter(lambda:app.state.clock()) if limiter is None else limiter
    app.add_middleware(SecurityBoundary,limiter=app.state.limiter)
    app.add_middleware(CORSMiddleware, allow_origins=settings.frontend_origins,
        allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"], expose_headers=["Retry-After"])

    @app.exception_handler(ImageInputError)
    async def image_input_error(request: Request, error: ImageInputError):
        return JSONResponse(status_code=400, content={"detail": "Image must be valid JPEG, PNG or WebP within the pixel limit."})

    @app.exception_handler(ImageStorageError)
    async def image_storage_error(request: Request, error: ImageStorageError):
        return JSONResponse(status_code=500, content={"detail": "Listing photo storage is temporarily unavailable." if request.url.path.startswith("/listings") else "Profile photo storage is temporarily unavailable."})

    @app.exception_handler(CsrfError)
    async def csrf_error(request: Request, error: CsrfError):
        return JSONResponse(status_code=403, content={"detail": "Request origin or CSRF token is invalid."})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # FastAPI's default error includes raw inputs; never return those.
        detail = {"/auth/register": "Invalid registration request.", "/auth/login": "Invalid login request.", "/auth/change-password": "Invalid password-change request.", "/auth/forgot-password": "Invalid recovery request.", "/auth/reset-password": "Invalid password-reset request.", "/users/me": "Invalid profile request."}.get(request.url.path, "Invalid verification request.")
        if request.url.path.startswith("/listings/"):detail = "Invalid listing-photo request." if "/photos" in request.url.path else "Invalid listing-edit request."
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        detail = "Registration is temporarily unavailable." if request.url.path == "/auth/register" else "Verification is temporarily unavailable." if request.url.path in {"/auth/verify-email", "/auth/resend-verification"} else "Profile is temporarily unavailable." if request.url.path == "/users/me" else "Listings are temporarily unavailable." if request.url.path.startswith("/listings") or request.url.path == "/categories" else "Authentication is temporarily unavailable."
        return JSONResponse(status_code=500, content={"detail": detail})

    app.include_router(admin_router)
    app.include_router(router)
    app.include_router(users_router)
    app.include_router(listings_router)
    app.include_router(listing_photos_router)
    from backend.openapi_contract import install_contract
    install_contract(app)
    return app
