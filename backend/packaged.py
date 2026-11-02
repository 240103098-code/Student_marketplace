"""Explicit packaged ASGI entry point; existing development factories stay unchanged."""

from pathlib import Path
import re

from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from backend.app import create_app
from backend.config import load_settings


class PackagedApp:
    def __init__(self, api, static_dir):
        self.api = api
        self.static_dir = Path(static_dir).resolve(strict=True)
        self.assets = StaticFiles(directory=self.static_dir / "assets", follow_symlink=False)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.api(scope, receive, send)
        path = scope["path"]
        if path == "/api" or path.startswith("/api/"):
            # Strip before every existing middleware/guard: request-size/rate-limit
            # routing must see the same canonical paths as separate-port mode.
            child = dict(scope, path=path[4:] or "/", raw_path=(path[4:] or "/").encode(), root_path="")

            async def prefixed_cookies(message):
                if message["type"] == "http.response.start":
                    message = dict(message, headers=[(key, value.replace(b"Path=/auth", b"Path=/api/auth") if key.lower() == b"set-cookie" else value) for key, value in message["headers"]])
                await send(message)
            return await self.api(child, receive, prefixed_cookies)
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        if path.startswith("/assets/") and scope["method"] in {"GET", "HEAD"}:
            child = dict(scope, path=path[7:], root_path="")
            try:
                async def static_headers(message):
                    if message["type"] == "http.response.start":
                        message = dict(message, headers=[*message["headers"], (b"x-content-type-options", b"nosniff"), (b"cache-control", b"public, max-age=3600")])
                    await send(message)
                return await self.assets(child, receive, static_headers)
            except HTTPException as error:
                if error.status_code != 404:
                    raise
        spa = path in {"/", "/login", "/register", "/verify", "/forgot-password", "/reset-password", "/marketplace", "/profile", "/my-listings", "/account/password", "/listings/new", "/admin", "/admin/users", "/admin/listings", "/admin/reports"} or re.fullmatch(r"/(?:admin/)?listings/[1-9][0-9]{0,18}(?:/edit)?", path)
        if spa and scope["method"] in {"GET", "HEAD"}:
            response = FileResponse(self.static_dir / "index.html", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        else:
            response = JSONResponse({"detail": "Not Found"}, status_code=404, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        await response(scope, receive, send)


def create_packaged_app():
    api = create_app(load_settings())
    # FastAPI docs reference the public prefix; business guards see stripped paths.
    api.root_path = "/api"
    return PackagedApp(api, Path(__file__).resolve().parent.parent / "static")
