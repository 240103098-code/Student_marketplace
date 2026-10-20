"""Optional local operator console for the SAME volatile API process."""
import threading
import time
import uvicorn
from backend.admin import main as provision
from backend.app import create_app
from backend.config import load_settings


def main():
    settings = load_settings()
    if settings.app_env == "production" or settings.database_url.get_secret_value() != "sqlite+pysqlite:///:memory:":
        raise SystemExit("This console requires explicit development/test SQLite memory configuration.")
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000,
        access_log=False, proxy_headers=False))
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    for _ in range(100):
        if server.started or not worker.is_alive():
            break
        time.sleep(.05)
    print("Volatile API on 127.0.0.1:8000. Commands: check, promote <verified university email>, stop.")
    try:
        while server.started and worker.is_alive():
            command = input("memory> ").strip()
            if command == "stop":
                break
            if command == "check":
                print("Database ready." if app.state.database.check_connection() else "Database unavailable.")
            elif command.startswith("promote "):
                provision(["--email", command[len("promote "):]], database=app.state.database)
            else:
                print("Commands: check, promote <verified university email>, stop.")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        server.should_exit = True
        worker.join()
        # Also handles a server that failed before entering ASGI lifespan.
        app.state.close_owned_resources()


if __name__ == "__main__":
    main()
