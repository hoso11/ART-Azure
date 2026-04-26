# Azure Web App for Containers — deployment guide (ART) — Docker Hub edition

Target:
`https://art-front-cwdxfzhgcccvcjeh.germanywestcentral-01.azurewebsites.net`

Images are published to **Docker Hub** under the `hoso30` namespace (public).

---

## 1. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Azure Web App for Containers (single plan, one instance)    │
│                                                              │
│  MAIN    art-frontend     Next.js 14, port 3000  ← public   │
│  sidecar art-backend      FastAPI + Alembic, port 8000       │
│  sidecar art-worker       Celery worker + beat (no port)     │
│  sidecar art-postgres     Postgres 16, port 5432             │
│  sidecar art-redis        Redis 7, port 6379                 │
│  sidecar art-minio        MinIO, port 9000                   │
│                                                              │
│  All containers share one network namespace → every hop is   │
│  127.0.0.1:<port>. Only the main container's port is public. │
└──────────────────────────────────────────────────────────────┘
```

### Request flow

- Browser → `https://…azurewebsites.net/` → Azure terminates TLS → main container (Next.js, `:3000`).
- Browser → `/api/v1/*` → Next.js rewrite (`next.config.js`) → `http://localhost:8000/api/v1/*` (backend sidecar).
- Next.js SSR server → `http://localhost:8000/api/v1/*` directly.
- Backend → Postgres `localhost:5432`, Redis `localhost:6379`, MinIO `localhost:9000`.
- Worker → Redis `localhost:6379`, Postgres `localhost:5432`, SMTP.

### Why no nginx

In local dev, nginx gave us rate limiting, `client_max_body_size`, and a single public port. In Azure, the platform's front door already terminates TLS and serves as the single public edge; `next.config.js` handles the `/api/*` → backend rewrite. Nginx would only add a hop.

---

## 2. Images — what is built vs. pulled

| Image | Source | Purpose | Sidecar(s) using it |
|---|---|---|---|
| `hoso30/art-frontend:TAG` | **built** from `frontend/Dockerfile.azure` | Next.js 14 standalone runtime | `art-frontend` (main) |
| `hoso30/art-backend:TAG`  | **built** from `backend/Dockerfile.azure`  | FastAPI + Celery (one image, two roles) | `art-backend`, `art-worker` |
| `postgres:16-alpine`      | Docker Hub (upstream, unchanged) | database | `art-postgres` |
| `redis:7-alpine`          | Docker Hub (upstream, unchanged) | broker + cache | `art-redis` |
| `minio/minio:latest`      | Docker Hub (upstream, unchanged) | object storage | `art-minio` |

Only two images are custom-built and pushed. The worker reuses the backend image with a different startup command — no separate build.

---

## 3. Local validation (before any push)

`docker-compose.azure.yml` mirrors the Azure sidecar topology locally: every service joins one network namespace via `network_mode: service:frontend`, so every inter-service call is `localhost:PORT` — exactly like Azure.

```bash
cd /c/Users/HP/Desktop/ART-Azure
cp .env.azure.example .env.azure
# Edit .env.azure: set SECRET_KEY, POSTGRES_PASSWORD, MINIO_SECRET_KEY.

docker compose -f docker-compose.azure.yml --env-file .env.azure up --build
```

Open:

- `http://localhost:3000/` — homepage
- `http://localhost:3000/api/v1/docs` — Swagger (proxied through Next.js to backend)
- `http://localhost:3000/login` — log in

Seed:

```bash
docker compose -f docker-compose.azure.yml --env-file .env.azure \
  exec backend python -m scripts.seed
```

Seed users: `admin@art-manufacturing.com / admin123456`, `john@mitchell-retail.com / user123456`.

Tear down:

```bash
docker compose -f docker-compose.azure.yml --env-file .env.azure down -v
```

If local passes, the images are Azure-ready.

---

## 4. Build & push to Docker Hub

You are already logged in as `hoso30`. Scripts live in `scripts/azure/` (PowerShell + bash variants).

### Quick path — one command

PowerShell:
```powershell
.\scripts\azure\release.ps1 -Tag v1
```

Bash (Git Bash / WSL):
```bash
TAG=v1 ./scripts/azure/release.sh
```

This builds both images and pushes them to `hoso30/art-frontend:v1` and `hoso30/art-backend:v1`.

### Build only

PowerShell:
```powershell
.\scripts\azure\build.ps1 -Tag v1
```

Bash:
```bash
TAG=v1 ./scripts/azure/build.sh
```

### Push only (after build)

PowerShell:
```powershell
.\scripts\azure\push.ps1 -Tag v1
```

Bash:
```bash
TAG=v1 ./scripts/azure/push.sh
```

### Manual equivalent (if you want to run docker directly)

```bash
# Backend
docker build -f backend/Dockerfile.azure -t hoso30/art-backend:v1 ./backend
docker push hoso30/art-backend:v1

# Frontend (NEXT_PUBLIC_* are baked in at build time)
docker build -f frontend/Dockerfile.azure \
  --build-arg NEXT_PUBLIC_APP_NAME="ART Manufacturing" \
  --build-arg NEXT_PUBLIC_API_URL="/api/v1" \
  --build-arg NEXT_PUBLIC_MINIO_URL="" \
  -t hoso30/art-frontend:v1 ./frontend
docker push hoso30/art-frontend:v1
```

Since the Docker Hub repo is public, Azure does not need pull credentials.

---

## 5. Azure Web App configuration

### Option A — Portal

1. **App Services → `art-front-cwdxfzhgcccvcjeh` → Deployment Center**
   - Source: **Docker Hub**.
   - Access type: **Public**.
   - Image and tag: `hoso30/art-frontend:v1`.
   - Save.
2. **Configuration → General Settings**
   - Stack: **Docker**.
   - Always On: **On**.
   - HTTPS Only: **On**.
   - FTP state: **Disabled**.
   - **Startup Command: leave blank.** The frontend image's `CMD` is `node server.js` and must run. Do NOT set `npm start` / `next start` — they don't work with `output: "standalone"` and will crash-loop the main container (the standalone build only ships `server.js`).
3. **Configuration → Application Settings** — add every setting from section 6 below. Especially `WEBSITES_PORT=3000`.
4. **Deployment Center → Containers (sidecars)** — click **+ Add** for each sidecar:

   | Name | Image source | Image | Target port | Startup command |
   |---|---|---|---|---|
   | `art-backend`  | Docker Hub (public) | `hoso30/art-backend:v1`    | `8000` | *(leave blank — image default)* |
   | `art-worker`   | Docker Hub (public) | `hoso30/art-backend:v1`    | `9999` | `celery -A app.worker.celery_app worker --beat --loglevel=info` |
   | `art-postgres` | Docker Hub (public) | `postgres:16-alpine`       | `5432` | *(leave blank)* |
   | `art-redis`    | Docker Hub (public) | `redis:7-alpine`           | `6379` | *(leave blank)* |
   | `art-minio`    | Docker Hub (public) | `minio/minio:latest`       | `9000` | `server /data` |

> **MinIO note.** Do NOT paste `server /data --console-address ":9001"` — Azure's shell parsing mangles the quoted `:9001` and MinIO fails with `Unable to split host port ":9001": invalid port number`. The console is unreachable in Azure anyway (only `WEBSITES_PORT` is public), so omit it. If you really want the console, use `server /data --console-address 0.0.0.0:9001` with no quotes.

   Notes:
   - `art-worker` doesn't listen on any port. Azure still requires `--target-port`; `9999` is an arbitrary unused value — nothing routes to it.
   - Only the MAIN container's `WEBSITES_PORT` is public.
   - **Do NOT wrap sidecar startup commands in `bash -c "…"`.** Azure adds its own shell wrapper and eats the outer quotes, yielding `unexpected EOF while looking for matching "'`. Use a single unnested command. The `--beat` flag lets one Celery worker process also run the Beat scheduler, which is fine for a single-instance deployment.
5. **Restart** the Web App.
6. **Log stream** to watch startup.

### Option B — Azure CLI

```bash
RG=rg-art-azure
APP=art-front-cwdxfzhgcccvcjeh

# Main container
az webapp config container set -g $RG -n $APP \
  --docker-custom-image-name docker.io/hoso30/art-frontend:v1

az webapp config set -g $RG -n $APP --always-on true

# Sidecars (az CLI ≥ 2.63 required for sitecontainers)
az webapp sitecontainers create -g $RG -n $APP --container-name backend \
  --image docker.io/hoso30/art-backend:v1 --target-port 8000 --is-main false

az webapp sitecontainers create -g $RG -n $APP --container-name worker \
  --image docker.io/hoso30/art-backend:v1 --target-port 9999 --is-main false \
  --start-up-command 'celery -A app.worker.celery_app worker --beat --loglevel=info'

az webapp sitecontainers create -g $RG -n $APP --container-name postgres \
  --image docker.io/library/postgres:16-alpine --target-port 5432 --is-main false

az webapp sitecontainers create -g $RG -n $APP --container-name redis \
  --image docker.io/library/redis:7-alpine --target-port 6379 --is-main false

az webapp sitecontainers create -g $RG -n $APP --container-name minio \
  --image docker.io/minio/minio:latest --target-port 9000 --is-main false \
  --start-up-command 'server /data --console-address ":9001"'

az webapp restart -g $RG -n $APP
```

---

## 6. Application Settings

Paste as JSON via **App Service → Configuration → Application Settings → Advanced edit**. Every setting below is injected into every container (main + all sidecars).

```json
[
  { "name": "WEBSITES_PORT",                       "value": "3000" },
  { "name": "WEBSITES_CONTAINER_START_TIME_LIMIT", "value": "600" },
  { "name": "WEBSITES_ENABLE_APP_SERVICE_STORAGE", "value": "false" },

  { "name": "APP_NAME",   "value": "ART Manufacturing" },
  { "name": "APP_ENV",    "value": "production" },
  { "name": "DEBUG",      "value": "false" },
  { "name": "LOG_FORMAT", "value": "json" },

  { "name": "SECRET_KEY",                      "value": "GENERATE_A_64_CHAR_RANDOM_STRING" },
  { "name": "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "value": "15" },
  { "name": "JWT_REFRESH_TOKEN_EXPIRE_DAYS",   "value": "7" },
  { "name": "ALLOWED_ORIGINS",                 "value": "https://art-front-cwdxfzhgcccvcjeh.germanywestcentral-01.azurewebsites.net" },

  { "name": "POSTGRES_USER",     "value": "art_user" },
  { "name": "POSTGRES_PASSWORD", "value": "CHANGE_ME" },
  { "name": "POSTGRES_DB",       "value": "art_manufacturing" },
  { "name": "DATABASE_URL",      "value": "postgresql+asyncpg://art_user:CHANGE_ME@localhost:5432/art_manufacturing" },
  { "name": "DATABASE_URL_SYNC", "value": "postgresql://art_user:CHANGE_ME@localhost:5432/art_manufacturing" },

  { "name": "REDIS_URL",             "value": "redis://localhost:6379/0" },
  { "name": "CELERY_BROKER_URL",     "value": "redis://localhost:6379/0" },
  { "name": "CELERY_RESULT_BACKEND", "value": "redis://localhost:6379/1" },

  { "name": "STORAGE_BACKEND",         "value": "minio" },
  { "name": "MINIO_ENDPOINT",          "value": "localhost:9000" },
  { "name": "MINIO_ACCESS_KEY",        "value": "minioadmin" },
  { "name": "MINIO_SECRET_KEY",        "value": "CHANGE_ME" },
  { "name": "MINIO_BUCKET",            "value": "art-images" },
  { "name": "MINIO_USE_SSL",           "value": "false" },
  { "name": "MINIO_EXTERNAL_ENDPOINT", "value": "localhost:9000" },

  { "name": "SMTP_HOST",    "value": "localhost" },
  { "name": "SMTP_PORT",    "value": "1025" },
  { "name": "SMTP_FROM",    "value": "noreply@art-manufacturing.com" },
  { "name": "SMTP_USE_TLS", "value": "false" },

  { "name": "INTERNAL_API_URL", "value": "http://localhost:8000" },
  { "name": "NODE_ENV",         "value": "production" }
]
```

### Settings classification

- **Required at runtime** (backend + worker won't start without them):
  `SECRET_KEY`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `STORAGE_BACKEND`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `ALLOWED_ORIGINS`, `APP_ENV`.
- **Required for the Azure platform**: `WEBSITES_PORT=3000` (must match main container's listen port).
- **Required for Next.js rewrite**: `INTERNAL_API_URL=http://localhost:8000`.
- **Optional / defaults are fine**: `APP_NAME`, `DEBUG`, `LOG_FORMAT`, `JWT_*`, `SMTP_*`, `MINIO_USE_SSL`, `MINIO_EXTERNAL_ENDPOINT`, `WEBSITES_CONTAINER_*`.
- **Build-time only (frontend image)** — NOT to be set as App Settings:
  `NEXT_PUBLIC_APP_NAME`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_MINIO_URL`. These are baked into the client bundle when the frontend image is built. **Changing them requires a frontend rebuild + push + redeploy.**

---

## 7. Sidecar details — what actually happens on boot

1. Azure starts all containers in parallel.
2. `art-postgres` (upstream image) initializes the DB on first boot and listens on `:5432`.
3. `art-redis` binds `:6379` within ~2s.
4. `art-minio` binds `:9000` within ~3s.
5. `art-backend` runs `alembic upgrade head` (Dockerfile.azure CMD) and then `uvicorn --workers 2`. Alembic retries transparently while Postgres is still coming up. Ready within 20–45s. The MinIO bucket `art-images` is auto-created and given public-read policy on first upload (see `backend/app/storage/minio_adapter.py`).
6. `art-worker` starts `celery worker` + `celery beat`. If Redis isn't ready yet, Celery retries.
7. `art-frontend` runs `node server.js` and listens on `:3000`. Ready in 3–5s.
8. Azure health probe against the main container on `WEBSITES_PORT=3000` succeeds → public URL serves traffic.

Sidecar filesystems are ephemeral. Postgres and MinIO data do NOT survive restarts, scale operations, or plan changes. For real production, swap to Azure Database for PostgreSQL + Azure Blob Storage (`STORAGE_BACKEND=azure`, set `AZURE_STORAGE_CONNECTION_STRING`).

---

## 8. Redeploy / update / restart

After you push a new image tag:

**Portal**:
- For the main container: **Deployment Center** → update the tag → Save.
- For a sidecar: **Deployment Center → Containers** → edit the sidecar row → update image/tag → Save.
- Click **Restart** on the Web App.

**CLI**:
```bash
az webapp config container set -g $RG -n $APP \
  --docker-custom-image-name docker.io/hoso30/art-frontend:v2

az webapp sitecontainers update -g $RG -n $APP --container-name backend \
  --image docker.io/hoso30/art-backend:v2

az webapp restart -g $RG -n $APP
```

If only App Settings changed, a restart is enough — no image change required.

---

## 9. Verification

After restart, confirm:

- `https://art-front-…/` renders the landing page.
- `https://art-front-…/api/v1/docs` shows Swagger.
- `https://art-front-…/login` → log in with the seed admin → redirect to `/dashboard`.
- **Log stream** (`az webapp log tail -g $RG -n $APP`) shows:
  - `art-backend`: `Uvicorn running on http://0.0.0.0:8000`.
  - `art-worker`: `celery@… ready.`
  - `art-frontend`: `- Local:        http://0.0.0.0:3000`.

Seed the database (first deploy only) via Kudu SSH on the backend sidecar:
```bash
python -m scripts.seed
```

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Public URL returns "Application Error" | Main container crashed or exceeded 230s startup | `az webapp log tail -g $RG -n $APP`; check frontend logs. Almost always a missing App Setting or wrong `WEBSITES_PORT` |
| `502 Bad Gateway` | Main container not listening on `WEBSITES_PORT` | Confirm `WEBSITES_PORT=3000`; frontend log must show bind on `:3000` |
| `/api/v1/*` returns 404 HTML from Next.js | Rewrite not in effect | Set `INTERNAL_API_URL=http://localhost:8000`; confirm `next.config.js` was shipped in the frontend image |
| Login succeeds but later calls return 401 | `Secure` cookie on non-HTTPS URL | The public URL must be HTTPS. Also check `ALLOWED_ORIGINS` matches exactly (scheme + host, no trailing slash) |
| Backend log: `connection refused` to `localhost:5432` | Postgres sidecar not yet ready on first boot | Harmless — Alembic retries. Persistent → verify `POSTGRES_*` vars match `DATABASE_URL` |
| Worker log: `kombu.exceptions.OperationalError` | Redis not ready | Harmless on first boot; persistent → verify `CELERY_BROKER_URL=redis://localhost:6379/0` |
| Product images show broken icons | Presigned URLs point at `localhost:9000` | Expected with the MinIO sidecar. Switch to `STORAGE_BACKEND=azure` + Blob Storage to fix |
| Image pull fails | Wrong image path | Must be `docker.io/hoso30/art-backend:TAG` (or `hoso30/art-backend:TAG` — Azure accepts both) |
| Sidecar looks up but backend can't reach it | Wrong `--target-port` | The declared port must match what the service inside actually listens on |
| Postgres data gone after redeploy | Sidecar FS is ephemeral | Expected. Re-seed via `python -m scripts.seed` in backend sidecar |
| `az webapp sitecontainers …` — command not found | Old az CLI | `az upgrade`; CLI ≥ 2.63 is required |
| NEXT_PUBLIC_* value didn't change after App Setting edit | Values are baked at build time | Rebuild frontend image with new `--build-arg`, push, redeploy |

Kudu (container exec, log stream, file explorer):
`https://art-front-cwdxfzhgcccvcjeh.scm.germanywestcentral-01.azurewebsites.net`

---

## 11. Checklist

- [ ] Logged into Docker Hub as `hoso30` (`docker login`).
- [ ] `.env.azure` created from `.env.azure.example` with strong secrets.
- [ ] Local Azure compose validated: `docker compose -f docker-compose.azure.yml --env-file .env.azure up --build` → login + dashboard work.
- [ ] `.\scripts\azure\release.ps1 -Tag v1` (or `./scripts/azure/release.sh`) succeeded — both images are on Docker Hub.
- [ ] App Service main container set to `hoso30/art-frontend:v1`.
- [ ] All 5 sidecars created (`backend`, `worker`, `postgres`, `redis`, `minio`) with correct ports and startup commands.
- [ ] `WEBSITES_PORT=3000` present in App Settings.
- [ ] Every required App Setting from section 6 populated (no `CHANGE_ME` left).
- [ ] `ALLOWED_ORIGINS` matches the public URL exactly.
- [ ] App Service restarted; log stream shows backend on `:8000`, worker `ready`, frontend on `:3000`.
- [ ] Browser: `/login` → login → `/dashboard` renders stats.

When every box ticks, Azure is live.
