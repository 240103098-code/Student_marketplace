FROM node:24.19.0-bookworm-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df AS frontend
WORKDIR /build
RUN npm install --global npm@12.2.0
COPY frontend/package.json frontend/package-lock.json ./
RUN PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci
COPY frontend/ ./
# The real build never imports these DEV-only modules. Exclude original mocks
# from the context; inert build-only placeholders allow static import resolution.
RUN printf 'export default function Disabled(){return null;}' > src/MockPanel.jsx \
 && printf 'export const mockService = null;' > src/mockService.js
RUN VITE_SERVICE_MODE=real VITE_API_PREFIX=/api npm run build

FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
 && groupadd --gid 10001 marketplace \
 && useradd --uid 10001 --gid marketplace --no-create-home marketplace \
 && mkdir /data && chown marketplace:marketplace /data
COPY backend/ ./backend/
COPY migrations/ ./migrations/
COPY migrations_sqlite/ ./migrations_sqlite/
COPY alembic.ini alembic-sqlite.ini ./
COPY --from=frontend /build/dist/ ./static/
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.packaged:create_packaged_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
