"""Uvicorn calls the runtime factory explicitly; imports do not load settings."""

from backend.app import create_app
from backend.config import load_settings


def create_runtime_app():
    return create_app(load_settings())
