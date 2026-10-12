"""Minimal application entry point without external service dependencies."""

from fastapi import FastAPI

from backend.routers import admin, auth, listings, users

app = FastAPI(title="Student Marketplace")

for router in (auth.router, users.router, listings.router, admin.router):
    app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
