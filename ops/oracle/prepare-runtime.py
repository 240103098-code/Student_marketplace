"""Root-only runtime configuration, outside source/build context; never prints secrets."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import socket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hostname")
    parser.add_argument("source_sha")
    parser.add_argument("proxy_image")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Root required")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", args.hostname):
        raise SystemExit("Invalid hostname")
    if not re.fullmatch(r"[a-f0-9]{40}", args.source_sha):
        raise SystemExit("Invalid source SHA")
    if not re.fullmatch(r"caddy:[0-9.]+-alpine@sha256:[a-f0-9]{64}", args.proxy_image):
        raise SystemExit("Proxy must use reviewed version and digest")
    socket.getaddrinfo(args.hostname, 443)
    os.umask(0o077)
    directory = Path("/etc/student-marketplace-demo")
    if directory.is_symlink():
        raise SystemExit("Unsafe runtime directory")
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.stat().st_uid != 0 or directory.stat().st_mode & 0o077:
        raise SystemExit("Unsafe runtime directory ownership/mode")
    target = directory / "runtime.env"
    if target.exists():
        raise SystemExit("Existing runtime secrets preserved; review explicit release update")
    password = secrets.token_hex(32)
    values = {
        "POSTGRES_DB": "marketplace",
        "POSTGRES_USER": "marketplace",
        "POSTGRES_PASSWORD": password,
        "DATABASE_URL": f"postgresql+psycopg://marketplace:{password}@db:5432/marketplace",
        "JWT_SECRET_KEY": secrets.token_hex(48),
        "FRONTEND_ORIGINS": json.dumps([f"https://{args.hostname}"], separators=(",", ":")),
        "APP_ENV": "production",
        "REFRESH_COOKIE_SECURE": "true",
        "MARKETPLACE_IMAGE": f"student-marketplace-demo:{args.source_sha}",
        "DEMO_HOSTNAME": args.hostname,
        "CADDY_IMAGE": args.proxy_image,
    }
    with target.open("x", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")
    print("Root-private runtime configuration generated; stable secrets retained on rerun.")


if __name__ == "__main__":
    main()
