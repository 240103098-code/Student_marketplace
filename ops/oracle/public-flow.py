"""Explicit operator-only real HTTPS flow; no mail fixtures or database bypass.

identity.json, session.json, cookies.txt and verification-code.txt belong in a
privately permissioned, Gitignored directory. Never include them in evidence.
"""
import argparse
import hashlib
import http.cookiejar
import json
import re
import struct
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zlib


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x20\x80\xc0" * 16) * 16)) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["register", "finish", "check"])
    parser.add_argument("origin")
    parser.add_argument("private_directory", type=Path)
    args = parser.parse_args()
    parsed = urlsplit(args.origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise SystemExit("Exact HTTPS origin required")
    if parsed.username or parsed.password:
        raise SystemExit("Origin must not contain credentials")
    directory = args.private_directory
    identity_path = directory / "identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if set(identity) != {"email", "password", "delivery_attempts"}:
        raise SystemExit("Private identity schema invalid")
    if not identity["email"].endswith("@sdu.edu.kz") or len(identity["password"]) < 12:
        raise SystemExit("Authorized university identity required")
    jar = http.cookiejar.MozillaCookieJar(str(directory / "cookies.txt"))
    if (directory / "cookies.txt").exists():
        jar.load(ignore_discard=True, ignore_expires=True)
    class OriginRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = urlsplit(newurl)
            if (target.scheme, target.netloc) != (parsed.scheme, parsed.netloc):
                raise urllib.error.URLError("Cross-origin/downgrade redirect refused")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), OriginRedirect())

    def request(path, method="GET", data=None, headers=None, expected=200):
        actual_headers = {"Origin": args.origin, **(headers or {})}
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            actual_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(args.origin + path, data=data, method=method, headers=actual_headers)
        try:
            response = opener.open(req, timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        final = urlsplit(response.geturl())
        if (final.scheme, final.netloc) != (parsed.scheme, parsed.netloc):
            raise SystemExit("Unexpected response origin")
        if response.status != expected:
            raise SystemExit(f"{method} {path}: status {response.status}; expected {expected}; no response details logged")
        body = response.read()
        print(f"{method} {path}: {response.status}")
        return response, body

    if args.stage == "register":
        if not 0 <= identity["delivery_attempts"] < 3:
            raise SystemExit("Authorized verification-message budget exhausted")
        # Increment before I/O: unknown delivery outcome never triggers blind retry.
        identity["delivery_attempts"] += 1
        identity_path.write_text(json.dumps(identity), encoding="utf-8")
        request("/api/auth/register", "POST", {"email": identity["email"], "password": identity["password"]}, expected=201)
        print("Normal registration accepted. User must privately enter received code; no inbox access.")
        return
    state_path = directory / "session.json"
    if args.stage == "finish":
        code = (directory / "verification-code.txt").read_text(encoding="utf-8-sig").strip()
        if not re.fullmatch(r"[0-9]{6}", code):
            raise SystemExit("Awaiting privately supplied six-digit code")
        request("/api/auth/verify-email", "POST", {"email": identity["email"], "code": code})
        response, body = request("/api/auth/login", "POST", {"email": identity["email"], "password": identity["password"]})
        cookie = response.headers.get("Set-Cookie", "")
        for required in ["Secure", "HttpOnly", "SameSite=lax", "Path=/api/auth"]:
            if required.lower() not in cookie.lower():
                raise SystemExit("Production cookie attribute check failed")
        state = {"access_token": json.loads(body)["access_token"]}
        auth = {"Authorization": "Bearer " + state["access_token"]}
        boundary = "marketplaceOwnedSyntheticImage"
        data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"synthetic.png\"\r\nContent-Type: image/png\r\n\r\n".encode()
                + png() + f"\r\n--{boundary}--\r\n".encode())
        request("/api/users/me/avatar", "POST", data, {**auth, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        _, avatar = request("/api/users/me/avatar", headers=auth)
        state["avatar_sha256"] = hashlib.sha256(avatar).hexdigest()
        state_path.write_text(json.dumps(state), encoding="utf-8")
        jar.save(ignore_discard=True, ignore_expires=True)
        (directory / "verification-code.txt").write_text("", encoding="utf-8")
        print("Production secure-cookie and actual private upload checks passed.")
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        # Demonstrate retained refresh-session recovery even if old access expired.
        _, csrf = request("/api/auth/csrf")
        _, refreshed = request("/api/auth/refresh", "POST", headers={"X-CSRF-Token": json.loads(csrf)["csrf_token"]})
        state["access_token"] = json.loads(refreshed)["access_token"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        jar.save(ignore_discard=True, ignore_expires=True)
        auth = {"Authorization": "Bearer " + state["access_token"]}
    request("/api/auth/me", headers=auth)
    response, avatar = request("/api/users/me/avatar", headers=auth)
    if "private" not in response.headers.get("Cache-Control", "") or "no-store" not in response.headers.get("Cache-Control", ""):
        raise SystemExit("Private photo cache policy mismatch")
    if hashlib.sha256(avatar).hexdigest() != state["avatar_sha256"]:
        raise SystemExit("Retained image byte hash mismatch")
    anonymous = urllib.request.build_opener(OriginRedirect())
    for path in ["/api/users/me/avatar", "/api/auth/me"]:
        try:
            anonymous.open(args.origin + path, timeout=20)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise SystemExit("Anonymous protected route denial mismatch")
        else:
            raise SystemExit("Anonymous protected route unexpectedly available")
    request("/uploads/synthetic.png", expected=404)
    # A bad Origin must fail even while holding a real session cookie.
    request("/api/auth/csrf", headers={"Origin": "https://untrusted.invalid"}, expected=403)
    _, csrf = request("/api/auth/csrf")
    _, refreshed = request("/api/auth/refresh", "POST", headers={"X-CSRF-Token": json.loads(csrf)["csrf_token"]})
    state["access_token"] = json.loads(refreshed)["access_token"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    jar.save(ignore_discard=True, ignore_expires=True)
    print("Actual session, image bytes, public denials, origin and refresh checks passed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        raise SystemExit("Public-flow check failed; inspect privately without logging credentials") from None
