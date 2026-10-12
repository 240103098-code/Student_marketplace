# Student Marketplace

A planned university-only marketplace where verified students list items and contact sellers externally.

The Python scaffold, typed configuration, PostgreSQL connection/session helpers, account/code/refresh-session schema, unverified-student registration with configured SMTP code delivery, and React preview shell are ready. One-time verification and sixty-second resend are available; verified-user login and short-lived Bearer access are also available; secure refresh rotation/logout are available; React registration/verification forms are ready; marketplace features and React login/session handling remain planned. Live university-inbox delivery awaits external SMTP setup. Python 3.11 or newer is supported (verified with Python 3.13.15). Create a virtual environment with `python -m venv .venv`, install pinned dependencies with `.venv/Scripts/python.exe -m pip install -r requirements.lock`, and run `.venv/Scripts/python.exe -m unittest discover -s tests -v` from the repository root on Windows. Real PostgreSQL tests require an explicitly confirmed disposable database; see the setup guide for preparation, migrations, and other platforms.

For the frontend, use Node 24.15.0+ on the 24.x line (verified with 24.19.0) or another manifest-supported version, and npm 12.2.0+. From `frontend`, run `npm ci`, `npm run test -- --run`, `npm run build`, and `npm run dev`. Open `http://127.0.0.1:5173/`; stop with Ctrl+C. Registration and verification forms call the configured API; login and marketplace views remain placeholders with no fabricated listing data. Set VITE_API_ORIGIN as described in the setup guide. The setup guide includes the workspace-local npm option used for verification.

## Project documents

- [MVP requirements](_docs/plan.md)
- [40-task backlog](_docs/tasks.md)
- [Development process](_docs/process.md)
- [Local setup and current status](_docs/local-setup.md)

## Planned stack

React, FastAPI, PostgreSQL, SQLAlchemy, and Alembic, with JWT authentication and university-email verification through configured email delivery.

## Project tracking

Use [GitHub Issues](https://github.com/240103098-code/Student_marketplace/issues) in [this repository](https://github.com/240103098-code/Student_marketplace). Follow the documented process one issue at a time. With runtime settings and PostgreSQL migrations configured, start the backend with `.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000`. Open `http://127.0.0.1:8000/docs` and stop with Ctrl+C. See [the registration API contract](_docs/api.md) and [local setup](_docs/local-setup.md); registration emails a verification code when SMTP is configured; accounts start unverified and can be activated through the verification endpoint; login issues a short-lived access token, and /auth/me checks current account/session-family eligibility. Refresh/logout use a protected HttpOnly cookie and Origin/CSRF checks documented in the API guide. Local SMTP protocol tests passed, while live internet inbox delivery has not been verified.
