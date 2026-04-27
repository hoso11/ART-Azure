# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

Everything runs inside Docker Compose; the `Makefile` is the canonical entry point.

- `make up` / `make up-build` — start the stack (postgres, redis, minio, migrate, backend, worker, frontend, nginx). `migrate` runs `alembic upgrade head` once, then the backend waits on it via `service_completed_successfully`.
- `make down` / `make clean` — stop; `clean` also drops volumes.
- `make migrate` — re-run migrations against the running DB.
- `make migration msg="add_foo"` — autogenerate a new Alembic revision.
- `make seed` — populate sample data via `python -m scripts.seed` inside the backend container.
- `make test` — `pytest tests/ -v` inside the backend container. Tests use a file-backed SQLite DB (`sqlite+aiosqlite:///./test.db`) via `dependency_overrides[get_db]`, so they do **not** touch Postgres. Run a single test with e.g. `docker-compose exec backend pytest tests/test_orders.py::test_name -v`. **When adding a new feature, also add a test in `backend/tests/test_<domain>.py` and run the full suite — see `backend/tests/README.md` for the layout and conventions. Do not declare a feature done while `make test` is red.**
- `make logs` / `make logs-backend` / `make logs-frontend` / `make logs-worker` — tail logs.
- `make shell` / `make shell-frontend` — exec into the container.
- Frontend lint/build (inside container): `docker-compose exec frontend npm run lint` / `npm run build`. There is no frontend test runner.

Entry URLs when the stack is up:
- `http://localhost/` — nginx → frontend (Next.js dev, HMR through nginx with WebSocket upgrade)
- `http://localhost/api/v1/...` — nginx → backend (rate-limited 30 r/s, burst 20)
- `http://localhost/api/v1/docs` — FastAPI Swagger
- `http://localhost:9001` — MinIO console

Seed credentials (from `scripts/seed.py`): `admin@art-manufacturing.com` / `admin123456`, `john@mitchell-retail.com` / `user123456`.

## Definition of done — pre-completion checklist (load-bearing)

Before declaring **any** task complete — feature, bug fix, refactor, doc-only — run these five checks. If any one fails, the task is not done. Fix the failure first; do not report success with caveats.

1. **Backend tests pass.**
   ```bash
   docker-compose exec backend pytest tests/ -q
   ```
   Required result: `N passed, 0 failed`. New feature? Also added a test for it (see `backend/tests/README.md`).

2. **Frontend type-check passes.**
   ```bash
   docker-compose exec frontend npx tsc --noEmit
   ```
   Required result: exit code 0. Treat any TypeScript error as a failure even if Next.js dev still serves the page.

3. **Zero Armenian-text violations in modified frontend files.** For every file you touched under `frontend/src/`:
   ```bash
   grep -rPn "[\x{0400}-\x{04FF}\x{0370}-\x{03FF}]" <files>
   ```
   Required result: no output. Cyrillic and Greek lookalikes are forbidden inside Armenian strings — see the Armenian UI text rules section.

4. **No broken imports or compilation errors.** The Next.js dev container should show clean recompiles for routes you touched:
   ```bash
   docker-compose logs --tail=20 frontend | grep -E "Compiled|error|Error"
   ```
   Required result: only `✓ Compiled` lines for affected routes; zero `error`/`Error` lines. The TypeScript check above catches type errors; this catches runtime import failures (missing files, circular imports, wrong default-vs-named exports).

5. **Audit logging on every new mutation.** Any new endpoint or service action that mutates state must call `await activity_service.log_activity(...)`. This applies to: **create, update, delete, status change, stock/material quantity change, report export, and production completion** (any operation that an admin would later want to ask "who did this?" about). Use the router-layer pattern — capture old snapshot before the mutation if a diff is needed, then call the helper after the mutation succeeds:
   ```python
   from app.activity import service as activity_service

   await activity_service.log_activity(
       db,
       user=admin,            # or None for failed-auth events
       request=request,       # FastAPI Request, captures IP via X-Forwarded-For
       action="<module>.<verb>",   # snake_case, e.g. "order.status_changed"
       entity_type="<module>",     # e.g. "order", "product", "production_batch"
       entity_id=...,
       old_values=..., new_values=..., details=...,
   )
   ```
   Rules: (a) `log_activity` never raises — safe to call from any path; (b) sensitive data (passwords, hashes, tokens) **never** goes into `old_values` / `new_values` — use a values-free `*.password_changed`-style action with `details="..."` instead; (c) for endpoints that raise after the mutation (e.g. failed login), `await db.commit()` before raising so the audit row survives `get_db`'s rollback; (d) add a matching label entry in `frontend/src/app/dashboard/activity/page.tsx` `ACTION_LABELS` so the UI renders human Armenian text. If audit logging is missing on a new mutation, the task is not complete — no "I'll add it in the next PR".

If you cannot run a check (e.g. the stack is down), say so explicitly in the final report — do not silently skip it. "I changed X and Y; tests not run because Docker isn't up" is acceptable; "task complete" without running these is not.

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

- **Two fetch helpers, split across two files — pick the right one AND import from the right path:**
  - **Server Components / Route Handlers → `import { serverFetch, serverGet } from "@/lib/api.server"`.** This module imports `next/headers` to read the `access_token` cookie and forwards it to `INTERNAL_API_URL` (container-network `http://backend:8000`). Uses `cache: "no-store"`.
  - **Client Components (`"use client"`) → `import { clientFetch } from "@/lib/api.client"`.** Hits `NEXT_PUBLIC_API_URL` (`/api/v1` via nginx) with `credentials: "include"` so the browser ships the cookie.
  - **Never import `@/lib/api.server` from a `"use client"` file.** The bundler walks the import graph; reaching `next/headers` from a client component fails `next build` (dev mode tolerates it, production build does not). This is why the file is split — keep it that way.
  - **Do not use the old `@/lib/api` path — it no longer exists.** The mixed file was deleted; any import from `@/lib/api` will fail to resolve.
- **Conventions for new frontend code** (apply to *new* code; do not retrofit existing call sites in unrelated PRs):
  - **New client-side API calls must use `clientFetch`** (from `@/lib/api.client`) — not raw `fetch("/api/v1/...")`. The helper handles the URL prefix and cookie/credentials wiring; bypassing it scatters the `/api/v1` prefix and auth setup across files. Older call sites still use raw `fetch`; converge them only when you're already touching the file.
  - **New list pages should use the existing reusable table components** (`components/ui/DataTable`, `Pagination`, `SearchInput`, `EmptyState`) or include a one-line code comment explaining why a hand-rolled `<table>` was needed. Several existing list pages predate this rule and hand-roll their tables; that's tolerated, not encouraged.
- **Auth gating is server-side.** `lib/auth.ts` exposes `getSession` (nullable), `requireAuth` (redirects to `/login`), `requireAdmin` (redirects non-admins to `/dashboard`). The dashboard `layout.tsx` calls `requireAuth` so every nested route is guarded at render time — don't re-check inside child pages.
- **Route tree** — `app/login`, `app/catalog` (public product browse), `app/dashboard/{orders,products,customers,inventory,production,reports,users,account}`. The `simple_user` side of the app relies on the service layer's customer-scoped filtering; the frontend does not enforce authorization itself.
- **Dev-only scripts** — `frontend/translate_admin.py` and `frontend/translate_fix.py` are ad-hoc utilities, not part of the app.

### Armenian UI text rules (load-bearing — read before touching any frontend string)

This project's UI is in Armenian. Garbled Armenian text is a recurring failure mode for LLM edits. These rules are non-negotiable:

1. **Use only Armenian Unicode (U+0531–U+058F).** Capital `Ա–Ֆ`, lowercase `ա–ֆ`. Currency sign `֏` (U+058F) is allowed inside Armenian strings.
2. **No transliteration.** Never write `Apranq` when the file says `Ապրանք`. Never write `Tarberake` when the file says `Տարբերակ`. If a place currently has Latin transliteration, leave it unless the user explicitly tells you to translate it.
3. **No fake/lookalike letters.** Cyrillic (`А Е О Р С Т Х`), Greek (`Α Ε Ο Ρ`), Latin look-alikes — all forbidden inside Armenian labels. They render correctly to the eye but break search, sort, copy-paste, and grep.
4. **All files UTF-8, no BOM.** Don't let an editor re-save anything as UTF-16 / cp1251 / Latin-1.
5. **After any frontend text edit, verify.** Run a Cyrillic / Greek scan on the files you touched:
   - PowerShell: `Select-String -Path <file> -Pattern '[Ѐ-ӿͰ-Ͽ]'`
   - Bash: `grep -rPn '[\x{0400}-\x{04FF}\x{0370}-\x{03FF}]' <file>`

   Zero matches required.
6. **Preserve user-provided wording exactly.** When the user dictates an Armenian string, paste it byte-for-byte. Do not "improve" spelling or grammar.
7. **Do not "fix" Armenian.** If a word looks misspelled to you, it almost certainly isn't — leave it. Only change Armenian text when the user explicitly asks for that text to change.
8. **When unsure, stop and ask.** If you can't tell whether a character is Armenian or Cyrillic, ask the user, or leave the original bytes untouched.

### Internal naming rules — English only (load-bearing)

Armenian belongs in the UI. **Everything technical stays in English `snake_case`.** No exceptions for "it's just a one-off field" or "it'll only be seen by admins" — once Armenian leaks into a column name, every ORM query, migration, JSON payload, and grep becomes a minefield.

The rule applies to:

- **Database table names** — `production_records`, not `արտադրության_գրառումներ`
- **Database column names** — `stock_quantity`, `fulfilled_from_stock`, `production_quantity`
- **Alembic migration filenames and revision IDs** — `006_order_item_fulfillment.py`, not `006_պատվեր_կատարում.py`
- **SQLAlchemy model class names and `__tablename__`** — `class ProductVariant`, `__tablename__ = "product_variants"`
- **Pydantic schema class names and field names** — `class OrderItemResponse`, `quantity: int`
- **API URL paths and query params** — `/api/v1/orders?status=confirmed`, not `/api/v1/պատվերներ?կարգավիճակ=...`
- **JSON request/response field names** — `{"product_id": 1, "stock_quantity": 5}`
- **Backend Python variable, function, and parameter names** — `def fulfill_order(...)`, not `def պատվերը_կատարել(...)`
- **Frontend TypeScript variable, type, and prop names** — `interface OrderItem { product_variant_id: number }`
- **Environment variables, Docker service names, config keys** — `DATABASE_URL`, not `ՏՎՅԱԼՆԵՐԻ_ՀԱՍՑԵ`

Allowed Armenian, by contrast:

- JSX text nodes and string literals shown to the user (`<h1>Պատվերներ</h1>`)
- The values inside label maps like `STATUS_LABELS` (the *keys* stay English: `confirmed`, `in_production`)
- Toast messages, error messages displayed to the user, button labels, table column headers
- Seed data values that represent actual user-visible content (a customer's `name` may be Armenian; the *column* is `name`)

Examples:

✓ Good
```python
class ProductVariant(Base):
    __tablename__ = "product_variants"
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)

# Frontend
<label>Քանակ</label>           # Armenian — UI text
<input name="stock_quantity"/>  # English — form field name
```

✗ Bad
```python
class ԱպրանքիՏարբերակ(Base):              # Armenian class name
    __tablename__ = "ապրանքի_տարբերակներ"  # Armenian table name
    քանակ: Mapped[int] = mapped_column(...)  # Armenian column name

# Frontend
<input name="քանակ"/>           # Armenian field name reaching the API
```

Rule of thumb: if the string ever crosses a network boundary, hits a database, appears in a `git log`, gets autocompleted by an IDE, or shows up in a stack trace — it must be English `snake_case`. If it's only ever rendered to a human, Armenian is fine.

### Edge / request flow

nginx (`nginx/nginx.conf`) is the single public entry on port 80:
- `/api/*`, `/health`, `/ready` → `backend:8000`
- everything else → `frontend:3000` (with HTTP/1.1 + `Upgrade`/`Connection` headers for Next.js HMR WebSockets)
- `client_max_body_size 50M` for image uploads.

The frontend talks to the backend **two different ways** in the same request cycle: server components go container-to-container via `INTERNAL_API_URL`; the browser goes through nginx via `NEXT_PUBLIC_API_URL`. Both paths must work — keep the cookie `path`/`samesite` settings compatible with both.

### Storage / deployment target

Designed for `docker-compose` local dev and Azure Web App deployment. The Azure Blob adapter is a placeholder in `app/storage/azure_adapter.py` — switch via `STORAGE_BACKEND=azure` and set the Azure env vars. Nothing else should need to change.
