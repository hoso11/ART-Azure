# Rollback Notes

What was rolled back from the failed v13 deployment, what must stay rolled back, and how to detect a regression.

## What was rolled back

### Migration `009_production_stage_rewrite`
- **Status: deleted from the repo.**
- It rewrote the production-stage data model. It failed in production for two reasons (see `KNOWN_RISKS.md` #1 and #4):
  1. PostgreSQL refused the enum CAST it attempted on `stagename` / `stagestatus`.
  2. Its 35-character revision id did not fit in `alembic_version.version_num` (`varchar(32)`).
- Recovery path used: widen `alembic_version.version_num` to `varchar(64)` via Path B SQL (provided to user out-of-band — DB-side only, not in the repo), then let the entrypoint guard rewrite any orphaned `009_*` stamp back to `006_order_item_fulfillment`, then `alembic upgrade head` brought the DB to `008_activity_log_columns`.

### Production-stage rewrite code
- The branch of `app/production/service.py` that paired with migration 009 was reverted.
- The rewrite version of `frontend/src/app/dashboard/production/StageStatusChange.tsx` was deleted and the original component restored.
- Any remaining helper code that only made sense alongside migration 009 was removed.

### Entrypoint fail-loud variant
- An interim version of `backend/entrypoint.sh` raised on unknown stamps instead of silently rewriting. That version was reverted; the current `entrypoint.sh` keeps the silent-rewrite-to-`006` behavior so already-deployed databases stamped at the orphaned `009_*` revision can self-heal on next boot.

## What must NOT be restored

Do not restore any of the following, even if a future task seems to need them:

1. **Any file at `backend/alembic/versions/009_*.py`.**
2. **The rewritten `ProductionStage` model** (the version that paired with migration 009 — different columns, different enum values).
3. **The rewritten `StageStatusChange.tsx`** that drove the per-stage UI against the rewritten model.
4. **Any code path that calls `ALTER TYPE stagename ...` or `ALTER TYPE stagestatus ...`.**
5. **Any Alembic revision id longer than 32 characters.**
6. **The `hoso30/art-backend:v13` image** as a runtime image, base layer, or cache source.

If the user explicitly asks for one of these, stop and re-read `KNOWN_RISKS.md` with them. The previous attempt failed in production; redoing it without addressing the underlying constraints will fail again.

## How to detect if migration 009 has accidentally reappeared

Run before any commit, deploy, or image publish:

```bash
# 1. No 009 migration file in the repo.
ls backend/alembic/versions/ | grep -E '^009' && echo 'STOP — 009 file present' || echo 'ok'

# 2. No 009 reference anywhere in the codebase (text search; one-line cautious read).
grep -rn '009_production_stage_rewrite\|009_production' backend/ frontend/ && echo 'STOP — 009 reference found' || echo 'ok'

# 3. Entrypoint whitelist still does NOT include 009.
grep -n '"009' backend/entrypoint.sh && echo 'STOP — 009 in whitelist' || echo 'ok'

# 4. Built image does not contain a 009 file.
docker run --rm <image-tag> ls /app/alembic/versions/ | grep -E '^009' && echo 'STOP — 009 in image' || echo 'ok'

# 5. Running database is not stamped at 009.
docker-compose exec backend alembic current
# Expected: 008_activity_log_columns (head)
# If you see 009_*, stop and consult — do not deploy on top of it.
```

All five must say `ok` (or, for #5, `008_activity_log_columns`). Any "STOP" finding means halt and surface to the user before doing anything else.

## How to detect if the v13 image has been pulled or referenced

```bash
# Local Docker images.
docker images hoso30/art-backend:v13

# Compose / Kubernetes / Azure manifests referencing :v13.
grep -rn 'art-backend:v13' . --exclude-dir=node_modules --exclude-dir=.git
```

If either returns a hit in deployable config, surface it to the user before any deploy step.

## Frontend image tags `v21`, `v22`, `v23` are also blacklisted

Three more frontend tags have been retired and must not be redeployed:

| Tag | Why | Detection |
|---|---|---|
| `art-frontend:v21` | Built from `frontend/Dockerfile` (dev mode `npm run dev`); crashed at runtime in Azure with `Module parse failed: Unexpected character '@'` on Tailwind globals.css under `NODE_ENV=production`. See `KNOWN_RISKS.md` #9. | `docker run --rm hoso30/art-frontend:v21 cat /app/package.json` shows the dev image still has source `.tsx` files instead of a prebuilt `.next/standalone`. |
| `art-frontend:v22` and `v23` | Built from Git Bash on Windows without `MSYS_NO_PATHCONV=1`; MSYS rewrote `--build-arg NEXT_PUBLIC_API_URL=/api/v1` to `C:/Program Files/Git/api/v1`, which webpack inlined into every `clientFetch` call. Every browser-side fetch threw `TypeError: Failed to fetch`. See `KNOWN_RISKS.md` #8. | `docker run --rm <tag> sh -c 'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'` returns matches. |

`terraform/envs/dev/variables.tf` validation rejects all three plus `v13`:

```hcl
condition     = !contains(["v13", "v21", "v22", "v23"], var.frontend_image_tag)
```

If a future tag is found to be poisoned, add it to that list immediately.

### Detection bundle for the frontend (run before deploying any new tag)

```bash
TAG=hoso30/art-frontend:vN

# 1. No MSYS path-mangled URL in any compiled JS.
docker run --rm "$TAG" sh -c 'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'
# Empty output required.

# 2. Image is a production standalone build (not the dev image).
docker run --rm "$TAG" sh -c 'ls /app/server.js' 
# Must list /app/server.js; an error here means it's the dev image — STOP.

# 3. Tailwind CSS was compiled at build time.
docker run --rm "$TAG" sh -c 'ls /app/.next/static/css/*.css | head -1'
# Must list at least one .css file; empty means PostCSS didn't run — STOP.
```

All three checks must pass before pushing the tag to Docker Hub or bumping `frontend_image_tag` in Terraform.

## RBAC ENUM extension is forward-only (v35 / v32, migration `012_extend_user_roles`)

Migration `012_extend_user_roles` extended the existing `userrole` Postgres ENUM with three new values via three idempotent statements:

```sql
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'director';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'production_manager';
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'warehouse_manager';
```

`downgrade()` is a documented no-op. **Postgres does not support `ALTER TYPE … DROP VALUE`** — once a value is in the type, removing it requires recreating the type and column, which is destructive (drop column → drop type → recreate type with original two values → recreate column → restore data).

### Rollback rule — read before flipping `backend_image_tag` below `v35`

A rollback to backend `:v34` (or any pre-v35 image) is **only data-safe if no `users.role` row holds one of the three new values.** v34's Pydantic `UserRole` enum and SQLAlchemy `Enum(UserRole)` mapping refuse to materialize unknown values. Symptoms of rolling back without preparing the DB:

- Login still works (token decode does not consult the DB enum).
- `GET /api/v1/users` raises 500 on the row with the unknown role.
- The users page errors out.

**Mandatory DB prep before rollback.** Connect via the `art_admin` DSN (`DATABASE_URL_SYNC`) and demote any non-original-role users back to `simple_user`:

```sql
UPDATE users SET role = 'simple_user'
WHERE role IN ('director', 'production_manager', 'warehouse_manager');
```

Verify with `SELECT id, email, role FROM users ORDER BY id;` — only `admin` / `simple_user` should appear. **Then** flip `backend_image_tag` in `terraform/envs/dev/terraform.tfvars` and apply.

### Live state snapshot (2026-05-02)

The live DB currently has **one** non-original-role row:

| ID | Email | Role | Notes |
|---|---|---|---|
| 7 | `art@art.am` | `director` | Smoke-test canary, intentionally created right after v35 came online to verify the new role works end-to-end. |

Any forced rollback today must include the demote step above. Don't forget the canary.

### Detection commands (run before any rollback below v35)

```bash
# 1. Read the live role distribution. Anything other than admin / simple_user means
#    a UPDATE is required before the rollback.
PGPASSWORD="$(terraform output -raw postgres_admin_password)" psql \
  "host=$(terraform output -raw postgres_fqdn) port=5432 dbname=art_manufacturing \
   user=art_admin sslmode=require" \
  -c "SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role;"

# 2. Confirm the ENUM has the new values (purely informational — they cannot be removed).
PGPASSWORD="$(terraform output -raw postgres_admin_password)" psql \
  "host=$(terraform output -raw postgres_fqdn) port=5432 dbname=art_manufacturing \
   user=art_admin sslmode=require" \
  -c "SELECT enumlabel FROM pg_enum
      JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
      WHERE pg_type.typname = 'userrole'
      ORDER BY enumlabel;"
# Expected output includes: admin, director, production_manager, simple_user, warehouse_manager.
```

### What must NOT be restored (RBAC forward-only addendum)

- Do not delete `backend/alembic/versions/012_extend_user_roles.py`.
- Do not propose a new migration that drops or recreates the `userrole` type to remove the three new values without explicit user approval and a documented data-preservation plan (`pg_dump`, parallel column, cutover).
- Do not narrow `UserRole` in `backend/app/users/models.py` back to two values — the model would reject any DB row using the new values, breaking `GET /users` even if no app code uses the new roles.

## If a "production stage rewrite" is genuinely needed in the future

Do not silently restore the rolled-back code. Treat it as a new design task:

1. Restate the goal in writing — what user-visible behavior is changing and why the current Option B aggregation is insufficient.
2. Propose a Postgres-safe enum migration plan (parallel column + backfill + cutover, not in-place enum alter).
3. Pick a revision id ≤ 32 characters.
4. Add the new revision id to the entrypoint whitelist *in the same commit*.
5. Test against Postgres (`make up && make migrate` against a clean volume), not just SQLite.
6. Get explicit user approval per `SAFE_TASK_RULES.md` #1 before generating the migration file.
