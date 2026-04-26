# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

Everything runs inside Docker Compose; the `Makefile` is the canonical entry point.

- `make up` / `make up-build` — start the stack (postgres, redis, minio, migrate, backend, worker, frontend, nginx). `migrate` runs `alembic upgrade head` once, then the backend waits on it via `service_completed_successfully`.
- `make down` / `make clean` — stop; `clean` also drops volumes.
- `make migrate` — re-run migrations against the running DB.
- `make migration msg="add_foo"` — autogenerate a new Alembic revision.
- `make seed` — populate sample data via `python -m scripts.seed` inside the backend container.
- `make test` — `pytest tests/ -v` inside the backend container. Tests use a file-backed SQLite DB (`sqlite+aiosqlite:///./test.db`) via `dependency_overrides[get_db]`, so they do **not** touch Postgres. Run a single test with e.g. `docker-compose exec backend pytest tests/test_orders.py::test_name -v`.
- `make logs` / `make logs-backend` / `make logs-frontend` / `make logs-worker` — tail logs.
- `make shell` / `make shell-frontend` — exec into the container.
- Frontend lint/build (inside container): `docker-compose exec frontend npm run lint` / `npm run build`. There is no frontend test runner.

Entry URLs when the stack is up:
- `http://localhost/` — nginx → frontend (Next.js dev, HMR through nginx with WebSocket upgrade)
- `http://localhost/api/v1/...` — nginx → backend (rate-limited 30 r/s, burst 20)
- `http://localhost/api/v1/docs` — FastAPI Swagger
- `http://localhost:9001` — MinIO console

Seed credentials (from `scripts/seed.py`): `admin@art-manufacturing.com` / `admin123456`, `john@mitchell-retail.com` / `user123456`.

## Architecture

B2B clothing-manufacturing platform. FastAPI + Next.js 14 App Router (SSR) + Postgres + Redis + Celery/Beat + MinIO, fronted by nginx. `.env` drives every service (see `.env.example`).

### Backend module layout (`backend/app/<domain>/`)

Every domain follows the same four-file split: `models.py` (SQLAlchemy 2.0 async, `Mapped[...]` syntax, inherits `app.database.Base`), `schemas.py` (Pydantic v2), `service.py` (DB logic, reusable across routers/workers/seed), `router.py` (thin HTTP layer). Domains: `auth`, `users`, `customers`, `products`, `orders`, `production`, `inventory`, `reports`, `activity`, plus cross-cutting `storage/` and `email/`. `main.py` mounts every router under `/api/v1`.

- **DB session** — `app.database.get_db` is an async generator that auto-commits on clean exit and rolls back on exception. Never commit manually inside service functions that are already inside a `get_db` scope; let the dependency close it. The engine uses `pool_pre_ping=True, pool_size=20, max_overflow=10`.
- **Auth** — JWT HS256 in two **httpOnly** cookies: `access_token` (path `/`, 15 min) and `refresh_token` (path scoped to `/api/v1/auth/refresh`, 7 days). `secure` is toggled on `APP_ENV=production`. `POST /auth/refresh` rotates both tokens. `GET /auth/me` is how the frontend validates sessions.
- **Authorization** — two roles on `User.role`: `admin` and `simple_user`. Enforce via FastAPI dependencies from `app.dependencies`: `get_current_user`, `require_admin`, `require_authenticated`. A `simple_user` is linked 1:1 to a `Customer` via `User.customer_id`; any service that lists orders/data for a non-admin **must** filter by `current_user.customer_id`. The B2B split of `User` ↔ `Customer` is load-bearing — do not merge them.
- **Errors** — raise the typed exceptions in `app.exceptions` (`NotFoundException`, `UnauthorizedException`, `ForbiddenException`, `ConflictException`, `ValidationException`). `app_exception_handler` renders them as `{detail, code}` with the right status. Don't raise bare `HTTPException` when a typed one exists.
- **Storage abstraction** — `app.storage.interface.StorageService` is an ABC with `upload_file`/`get_file_url`/`delete_file`. `get_storage_service()` dispatches on `STORAGE_BACKEND` env var (`minio` | `azure`). Use the factory; never import an adapter directly. `MINIO_EXTERNAL_ENDPOINT` (host-visible) differs from `MINIO_ENDPOINT` (container-network) — presigned URLs must use the external one.
- **Email abstraction** — same pattern in `app.email` (SMTP adapter today).
- **Celery** — `app.worker.celery_app` is the app; tasks live in `app.worker.tasks` and are routed to named queues: `images`, `notifications`, `reports`, `default`. Beat schedule is in `app.worker.beat_schedule` (currently: `daily_stock_check` at 06:00 UTC). The `worker` service in `docker-compose` runs worker + beat in one container via `bash -c "... & ... & wait"`.
- **Migrations** — Alembic is the source of truth; `001_initial.py` is the baseline. The `migrate` compose service blocks the `backend` and `worker` until it exits successfully.
- **Logging** — `loguru`, configured in `main.py`. `LOG_FORMAT=json` switches to structured JSON (use in production); `pretty` is the dev default. `RequestLoggingMiddleware` logs every request.

### Frontend (`frontend/src/`)

Next.js 14 App Router with **SSR-first** data fetching. Stack is intentionally lean: `next`, `react`, `recharts`, `tailwindcss` — no data-fetching library, no component library.

- **Two fetch helpers in `lib/api.ts`** — pick the right one:
  - `serverFetch`/`serverGet` (Server Components, Route Handlers) reads the `access_token` cookie via `next/headers` and forwards it to `INTERNAL_API_URL` (container-network `http://backend:8000`). Uses `cache: "no-store"`.
  - `clientFetch` (browser) hits `NEXT_PUBLIC_API_URL` (`/api/v1` via nginx) with `credentials: "include"` so the browser ships the cookie. Never call `serverFetch` from a client component.
- **Auth gating is server-side.** `lib/auth.ts` exposes `getSession` (nullable), `requireAuth` (redirects to `/login`), `requireAdmin` (redirects non-admins to `/dashboard`). The dashboard `layout.tsx` calls `requireAuth` so every nested route is guarded at render time — don't re-check inside child pages.
- **Route tree** — `app/login`, `app/catalog` (public product browse), `app/dashboard/{orders,products,customers,inventory,production,reports,users,account}`. The `simple_user` side of the app relies on the service layer's customer-scoped filtering; the frontend does not enforce authorization itself.
- **Dev-only scripts** — `frontend/translate_admin.py` and `frontend/translate_fix.py` are ad-hoc utilities, not part of the app.

### Edge / request flow

nginx (`nginx/nginx.conf`) is the single public entry on port 80:
- `/api/*`, `/health`, `/ready` → `backend:8000`
- everything else → `frontend:3000` (with HTTP/1.1 + `Upgrade`/`Connection` headers for Next.js HMR WebSockets)
- `client_max_body_size 50M` for image uploads.

The frontend talks to the backend **two different ways** in the same request cycle: server components go container-to-container via `INTERNAL_API_URL`; the browser goes through nginx via `NEXT_PUBLIC_API_URL`. Both paths must work — keep the cookie `path`/`samesite` settings compatible with both.

### Storage / deployment target

Designed for `docker-compose` local dev and Azure Web App deployment. The Azure Blob adapter is a placeholder in `app/storage/azure_adapter.py` — switch via `STORAGE_BACKEND=azure` and set the Azure env vars. Nothing else should need to change.
