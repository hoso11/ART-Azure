# Known Risks

These are the failure modes that have already cost us a deployment. Read before proposing any change in the listed areas.

## 1. Migration `009_production_stage_rewrite` must not be reintroduced

What happened: an earlier attempt to rewrite the production-stage data model shipped as Alembic revision `009_production_stage_rewrite` (revision id 35 chars long). Deploying it to Azure broke the database for two independent reasons:

1. **PostgreSQL enum CAST failure.** The migration converted the `stagename` / `stagestatus` enum columns and the data coercion was not safe — Postgres refused the cast on existing rows.
2. **`alembic_version.version_num` is `varchar(32)`** in the baseline schema. Revision id `009_production_stage_rewrite` is 35 characters, so even the *stamp* could not be written.

Both issues required emergency rollback. The migration file has been deleted from the repo and the production-stage rewrite code reverted.

**Rules:**
- Do not re-create a `009_*` (or any) migration that rewrites production stages.
- Do not reintroduce the rewritten `ProductionStage` model or the `StageStatusChange` rewrite component logic that paired with it.
- If a future task genuinely needs a production-data-model change, propose it in writing first, with a Postgres-safe enum migration plan and a revision id that fits in `varchar(32)`. See `SAFE_TASK_RULES.md`.
- The current Production page's one-row-per-order behavior is implemented at the **API layer** (Option B). No DB migration was required. See `NEXT_TASKS.md` and `ROLLBACK_NOTES.md`.

## 2. The `hoso30/art-backend:v13` cached image is poisoned

The published image tag `:v13` was built from the failed-009 code. **It is not the same as the current local code.**

**Rules:**
- Do not redeploy `:v13`.
- Do not pull `:v13` as a build cache layer.
- Before publishing a new image tag, build fresh from the current commit (`docker build --no-cache`) and verify migration 009 is absent in the resulting image.
- Verification: `docker run --rm <new-tag> ls /app/alembic/versions/ | grep 009` — must return nothing.

## 3. Entrypoint whitelist silently rewrites unknown stamps

`backend/entrypoint.sh` runs a Python guard at boot that reads `alembic_version.version_num`. If the value is not in the whitelist (currently `001..004, 006, 007, 008, 010_batch_partial_outcome, 011_order_stock_deducted, 012_extend_user_roles`), it **silently rewrites** the row to `006_order_item_fulfillment` and continues.

This was deliberate — it allowed Azure databases stamped at a removed revision (`005_production_records`, transient `009_*`) to recover without manual SQL. But it has two sharp edges:

- **A real future migration at `009`/`010`/etc. will be silently downgraded** unless its revision id is added to the whitelist *before* deploying. Whenever a new Alembic file lands, update both the file and the whitelist in the same commit.
- The rewrite is silent in stdout but the prior stamp is logged as `[entrypoint] migration guard: stamped <old> -> 006_...`. Anyone debugging an unexpected schema state should grep container logs for `migration guard:` first.

**Rules:**
- Adding a new migration? Add its revision id to the whitelist in `backend/entrypoint.sh` in the **same commit** as the migration file.
- Never propose removing the guard without a migration plan for any DB still stamped at a removed revision.
- Never extend the whitelist with revision ids longer than 32 characters (see risk #1).

## 4. PostgreSQL enum + `varchar(32)` lessons

Two systemic constraints that bit us once and will bite again:

- **`alembic_version.version_num` is `varchar(32)`** in the baseline schema. Every Alembic revision id must fit. Use short slugs: `010_short_name`, not `010_long_descriptive_explanation_of_change`.
- **Postgres enum types (`stagename`, `stagestatus`) cannot be `ALTER`ed casually.** Renaming a value, dropping a value, or changing a column from text→enum / enum→text needs an explicit `USING <expr>::<type>` cast and frequently a temp column. Test the migration against a Postgres copy — SQLite (used by tests) silently accepts enum changes that Postgres rejects.

**Rules:**
- Keep new revision ids ≤ 32 chars.
- Any migration touching `stagename` / `stagestatus` (or any enum) must be tested against Postgres before it ships, not just against the SQLite test DB. See `SAFE_TASK_RULES.md`.
- Prefer adding nullable columns and back-filling over altering enum types in place.

## 5. Production page one-row-per-order — fragile invariant

The current Production page shows one row per order. This is computed in Python at the API layer (`list_one_per_order` + `compute_current` in `backend/app/production/service.py`), not enforced in the DB. The underlying data still has 5 `ProductionStage` rows per order.

**The "single-in-progress invariant" is enforced only by `set_order_current`.** If anyone writes to `ProductionStage.status` through any other code path (a script, a new endpoint, a direct SQL update), they can leave an order with two `in_progress` rows, and the computed-current rule will pick the rightmost one — silently masking the inconsistency.

**Rules:**
- Any new write to `ProductionStage.status` must go through `production_service.set_order_current(...)` or explicitly preserve the invariant.
- The legacy per-row endpoints (`PATCH /production/{stage_id}`) still exist for backward compatibility — see test `test_legacy_per_row_endpoints_still_work`. Do not remove them in a single PR; deprecate first.
- Do not "fix" the invariant by adding a DB constraint without consulting the rollback notes — a DB-level constraint here is what migration 009 was attempting.

## 6. Local main Postgres DB has a stale Alembic stamp from the v13 rollback

The local `art_manufacturing` database is stamped at `006_order_item_fulfillment` while its schema already contains the tables and columns that 007 and 008 added. This is a leftover of the v13 rollback — the entrypoint guard rewrote the stamp back to 006 after migrations 007/008 had already been applied to the schema.

Consequence: running `alembic upgrade head` against the local main DB hits `psycopg2.errors.DuplicateTable: relation "production_batches" already exists` from migration 007. **This is not a problem with migration 010** — verified end-to-end on a clean `art_migration_test` Postgres DB (full chain `001 → ... → 010_batch_partial_outcome` ran without error, columns and server defaults verified, downgrade reverses cleanly). The same image deploying to a fresh production database works.

**Rules:**
- Do not interpret a `DuplicateTable` failure on the local main DB as a migration-010 bug. Reproduce on a clean DB first.
- The local fix is a one-line stamp update: `UPDATE alembic_version SET version_num = '008_activity_log_columns'` against `art_manufacturing`, then `alembic upgrade head` will apply only 010. **This is a destructive write to the main local DB — get explicit user approval before running it.** Recommended alternative: `make clean` (drops volumes, but loses any local data) then `make up`.
- When verifying a future migration on Postgres, prefer the **temp-DB pattern**: `CREATE DATABASE art_migration_test`, run `alembic upgrade head` against it via `DATABASE_URL_SYNC` override, verify, `DROP DATABASE`. Does not touch the main DB.

## 7. Production damaged-stock partial outcome — design is load-bearing

The Khotan feature uses **per-unit quantities** on `ProductionBatch`, not a whole-batch enum. This is intentional and replaced an earlier whole-batch `outcome ∈ {"good","defective"}` design that shipped in a transient `010_batch_outcome` migration before being scrapped pre-merge.

**Rules:**
- Never introduce a single-outcome enum or boolean on `ProductionBatch`. The fields are `good_quantity`, `damaged_quantity`, `defect_reason`. The endpoint is `PATCH /production/batches/{id}/complete` with both quantities in the body.
- Never resurrect `PATCH /production/batches/{id}/reject` or `BatchRejectRequest`. The "all damaged" case is `{good_quantity: 0, damaged_quantity: <quantity_to_produce>}`.
- Never create or reuse a `009_*` migration (also covered in risk #1) — migration 010 must remain the latest, and any future addition to this area should be `011_*` or higher with the same INT/TEXT discipline.
- Never touch `ProductionStage`, `StageName`, or `StageStatus` enums in the same migration as a Khotan-related change. Keep schema changes scoped to `production_batches` and `product_variants` columns. Touching the production-stage enums is the failure mode that broke v13.
- Never display, sum, or roll `damaged_stock_quantity` into sellable-stock reads (catalog, order fulfillment, inventory totals, the `Մնացորդ` column). The two counters are deliberately separate and must stay separate.
- Order-based damaged production is **Phase 2 and explicitly off the roadmap** until a product decision is made — see `NEXT_TASKS.md` "Open" section. Do not modify `OrderItem` or any order/production-stage code path in pursuit of damaged tracking without that approval.

## 8. MSYS path-mangling on Windows poisons docker `--build-arg` for path-shaped values (v22 / v23 incident)

What happened: `art-frontend:v22` and `v23` were built from Git Bash on Windows with `docker build --build-arg NEXT_PUBLIC_API_URL=/api/v1 …`. MSYS / Git Bash automatically converts arguments that start with `/` into Windows paths before they reach the docker CLI, so `/api/v1` became `C:/Program Files/Git/api/v1`. That value got `ENV`-set inside the build stage and webpack inlined it into every `clientFetch` call. In the browser:

```js
fetch("".concat("C:/Program Files/Git/api/v1").concat("/products?limit=100"), …)
```

`fetch()` throws `TypeError: Failed to fetch` for that URL. SSR was unaffected because the server uses the separate `INTERNAL_API_URL` (an `https://…` value, not path-shaped). The bug was invisible until somebody opened a feature that needs client-side fetch (the production modal product dropdown).

**Rules:**

- When building any image from Git Bash on Windows, **always** set `MSYS_NO_PATHCONV=1`:
  ```bash
  MSYS_NO_PATHCONV=1 docker build -f frontend/Dockerfile.azure -t hoso30/art-frontend:vN \
    --build-arg "INTERNAL_API_URL=https://app-art-backend-dev-art4242.azurewebsites.net" \
    --build-arg "NEXT_PUBLIC_API_URL=/api/v1" \
    --build-arg "NEXT_PUBLIC_APP_NAME=ART Manufacturing" \
    ./frontend
  ```
- Or omit `--build-arg NEXT_PUBLIC_API_URL=/api/v1` entirely — `Dockerfile.azure` already declares `ARG NEXT_PUBLIC_API_URL="/api/v1"`. Defaults written inside the Dockerfile are not subject to MSYS rewriting.
- Or run docker from PowerShell or cmd, which don't path-mangle.
- After every frontend image build, before pushing, verify:
  ```bash
  docker run --rm hoso30/art-frontend:vN sh -c \
    'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'
  ```
  Empty output is required. Any match means the build is poisoned — do not push, do not bump the Terraform tag.
- `terraform/envs/dev/variables.tf` blacklists `v22` and `v23` so they cannot be redeployed accidentally. Any future poisoned tag should be added to that blacklist immediately.

## 9. Frontend production builds must use `Dockerfile.azure`, never `Dockerfile`

What happened: `art-frontend:v21` was built using `frontend/Dockerfile` (the dev image, single-stage, `CMD ["npm", "run", "dev"]`). When deployed to Azure Web App with the platform's default `NODE_ENV=production`, `next dev`'s webpack pipeline could not resolve PostCSS / Tailwind plugins from `devDependencies`, so `globals.css` reached webpack's CSS parser still containing `@tailwind` directives and threw `Module parse failed: Unexpected character '@'`. The site rendered the Next.js error overlay instead of the app.

**Rules:**

- Production frontend images must be built from `frontend/Dockerfile.azure` (multi-stage: `deps → build (runs next build) → runtime`). The runtime stage ships `.next/standalone/server.js` and `.next/static/css/*.css` — Tailwind is already compiled into a flat CSS file at image-build time, no runtime PostCSS needed.
- `frontend/Dockerfile` is for local docker-compose dev only. Never tag it as `hoso30/art-frontend:vN` and push.
- `art-frontend:v21` is blacklisted in `terraform/envs/dev/variables.tf`.

## 9a. slowapi `headers_enabled=True` + dict-return endpoints (v26 incident)

`slowapi`'s `_inject_headers` expects every response to be a `starlette.responses.Response` instance. FastAPI route handlers that `return {...}` (a dict) cause Starlette to wrap them in a `JSONResponse` later in the middleware chain — but `_inject_headers` runs *earlier* and raises `Exception: parameter response must be an instance of starlette.responses.Response` if `headers_enabled=True` (the default). The exception aborts the response, the rate-limiter short-circuits silently, and the limit never fires.

`art-backend:v26` shipped this bug. Detected via local `TestClient` probe.

**Rules:**

- The Limiter in `backend/app/rate_limit.py` must be instantiated with `headers_enabled=False`. Don't flip it to True without confirming every rate-limited route returns a `Response` instance (none do today).
- Tests in `backend/tests/test_auth_surface_hardening.py` lock the `_headers_enabled` attribute to `False` — keep them green.
- v26 is blacklisted in `terraform/envs/dev/variables.tf`.

## 9b. XFF port-stripping on Azure App Service (v27 incident)

Azure App Service's front-end prepends an ephemeral source port to each `X-Forwarded-For` entry, e.g. `203.0.113.5:64923`. slowapi keys rate-limit buckets by the raw XFF entry, so every TCP connection (i.e. every curl request) lands in a fresh bucket and the rate limit never fires.

`art-backend:v27` shipped without port-stripping. Detected by trying to flood `/auth/login` from a single source and seeing zero `429`s after 30 attempts.

**Rules:**

- `_client_ip` in `backend/app/rate_limit.py` must strip `:port` from each XFF entry (preserving IPv6 brackets). Tests lock the behavior in `test_auth_surface_hardening.py::test_client_ip_*`. Keep them green.
- v27 is blacklisted in `terraform/envs/dev/variables.tf`.

## 10. Critical Data Protection — PostgreSQL & Azure Blob Storage are guarded twice

The four data resources (`azurerm_postgresql_flexible_server.this`, `azurerm_postgresql_flexible_server_database.app`, `azurerm_storage_account.images`, `azurerm_storage_container.images`) are protected by two independent layers, both in `terraform/envs/dev/main.tf`:

1. **Lifecycle `prevent_destroy = true`** on all four resources. Any plan that would destroy or replace one fails before apply with `Error: Instance cannot be destroyed`.
2. **Azure resource locks** (`CanNotDelete`) on the Postgres server and the Storage Account. The locks inherit to the database and the container, so two locks cover all four resources. Locks block DELETE via portal, `az` CLI, ARM API, and Terraform itself; they allow reads and updates so image-tag bumps, app-setting changes, and key rotations are unaffected.

**Why both layers:** `prevent_destroy` blocks Terraform-driven destroy/replace; the Azure lock blocks out-of-band deletes (portal click, manual `az` invocation, runaway script). With `prevent_destroy` alone, anyone who edits the lifecycle line can apply a destroy. With the lock alone, Terraform itself can destroy the lock first and then the resource. Together: a destroy needs **two** explicit config edits plus user approval at each step.

**Rules:**

- Never remove either layer without explicit user approval naming the resource.
- Never change `lock_level` from `CanNotDelete` to `ReadOnly` — `ReadOnly` blocks normal updates and breaks image deployments.
- Before every `terraform apply`, scan the plan and report whether any protected resource is touched (`-/+`, `- destroy`). The expected steady-state plan for an image-tag bump or app-setting change is `1 to change, 0 to add, 0 to destroy` against the Web App resources only — the four protected resources should not appear at all.
- The only foreseen legitimate recreate is the "PostgreSQL → West Europe" move when the `LocationIsOfferRestricted` subscription block lifts (see KNOWN_RISKS.md region exception). The recreate sequence is documented in `handoff/SAFE_TASK_RULES.md` Critical Data Protection section — `pg_dump` first, then layered config edits, then `pg_restore`, then re-protect.

## 11. Two-stage apply when adding SystemAssigned identity to an existing Web App

When `identity { type = "SystemAssigned" }` is added to an **existing** `azurerm_linux_web_app`, Terraform's planner sees `<resource>.identity[0]` as null in the pre-apply state (the state-side list is `[]` until apply completes). Any other resource that references `<resource>.identity[0].principal_id` in the same plan errors with `Missing required argument: principal_id`. A `count = length(...) > 0 ? 1 : 0` guard does NOT fix it — the planner resolves the principal_id expression eagerly even with count 0.

This fired during Task C2a when adding the `Storage Blob Data Contributor` role assignment.

**Rules:**

- For retrofitting MI onto an already-deployed Web App, gate dependent resources behind a tfvars-toggled bool (`var.enable_storage_role_assignment` is the canonical example). Default `false`; flip to `true` in tfvars only after the first apply has created the identity. Document in `terraform/envs/dev/README.md` "Task C2a two-stage apply".
- Do not change `enable_storage_role_assignment` from `true` to `false` in the dev tfvars — it would plan a destroy of the role assignment and break the running backend's MI auth.
- For greenfield envs where the Web App is being CREATED with identity, the bool can be `true` from the start; `identity[0].principal_id` is correctly marked "known after apply" when the parent is in the plan-add set, and Terraform creates the role assignment in the same pass.

## 12. `storage_use_azuread` + `shared_access_key_enabled = false` are a paired requirement

`azurerm_storage_account`'s Read step always tries to fetch four data-plane sub-property blocks (`queue_properties`, `share_properties`, `static_website`, `blob_properties`) using the storage account's shared key. With `shared_access_key_enabled = false`, those reads 403 with `KeyBasedAuthenticationNotPermitted` on every plan/refresh — the provider gets stuck and you can't even plan to re-enable the key.

This fired during Task C2b: the first apply succeeded in flipping `shared_access_key_enabled` on Azure side, but the post-modify refresh failed and left the saved plan stale. Recovered by adding `storage_use_azuread = true` to `provider "azurerm"` in `providers.tf`, then `terraform init -upgrade`, then re-plan/apply.

**Rules:**

- When disabling shared keys (`shared_access_key_enabled = false`), set `storage_use_azuread = true` on the azurerm provider in the **same edit**.
- The SP must hold a Storage data-plane RBAC role on each storage account it touches — `Storage Blob Data Reader` is sufficient; `Storage Blob Data Contributor` / `Storage Blob Data Owner` also work. Subscription-scope Owner satisfies this transitively (current state).
- If the SP is downgraded to Resource Manager `Contributor` only (control-plane), grant explicit `Storage Blob Data Owner` on `azurerm_storage_account.images` BEFORE the downgrade or all subsequent plans 403. See `handoff/SAFE_TASK_RULES.md` "Service Principal role for Terraform".
- Do not remove `storage_use_azuread = true` from `providers.tf` while `shared_access_key_enabled = false`. The pair is required.

## 14. RBAC userrole ENUM is forward-only — rollback to a pre-v35 backend is conditional

What changed: migration `012_extend_user_roles` added `director`, `production_manager`, `warehouse_manager` to the existing `userrole` Postgres ENUM via three idempotent `ALTER TYPE userrole ADD VALUE IF NOT EXISTS …` statements. The migration is non-destructive and idempotent on the way up. **It is forward-only** — Postgres does not support `ALTER TYPE … DROP VALUE`, so the new values cannot be removed without dropping and recreating the type and column, which is destructive.

What this means for rollback: a code rollback to backend `:v34` (or any pre-v35 image) is only data-safe **if no `users.role` row holds one of the three new values**. v34's Pydantic `UserRole` enum and SQLAlchemy `Enum(UserRole)` mapping refuse to materialize unknown values, so:

- Login still works (token decode does not consult the DB enum until a query touches `users`).
- `GET /api/v1/users` raises 500 on the row whose role is unknown to the model.
- The users page errors out.

**Rules:**

- Before forcing a rollback to v34 / v31 (or any pre-RBAC backend), demote every non-original role back to `simple_user` via the `art_admin` DSN:
  ```sql
  UPDATE users SET role = 'simple_user'
  WHERE role IN ('director', 'production_manager', 'warehouse_manager');
  ```
  Run this against the live DB *before* flipping `backend_image_tag` in tfvars. The rollback is otherwise safe (cookies issued by v35 stay valid against v34; the JWT carries the role string but `get_current_user` re-reads the DB on each request).
- Live DB currently contains **one** non-original-role row: user id 7, `art@art.am`, role `director`. This was created intentionally as a smoke-test canary right after v35 came online. Any forced rollback today must include the demote step above. Don't forget the canary.
- Do not attempt to remove the new ENUM values via ad-hoc SQL or a "downgrade" migration. The recreate sequence is destructive (drop column → drop type → recreate type with the original two values → recreate column → restore data) and is not part of any rollback plan in this repo.
- Future agents: do not propose deleting migration 012, deleting `director` / `production_manager` / `warehouse_manager` from `UserRole`, or shrinking the role groups in `backend/app/dependencies.py` without first reading `ROLLBACK_NOTES.md` "RBAC ENUM extension is forward-only".

## 13. Sensitive files in the repo (load-bearing — read before any commit)

Three files contain secrets that the deployment depends on. All three are gitignored. Compromising any of them is a security incident:

| File | Sensitive content | Impact of leak |
|---|---|---|
| `terraform/envs/dev/.env.terraform` | `ARM_*` Service Principal credentials | Full subscription control. |
| `terraform/envs/dev/terraform.tfvars` | `backend_secret_key` (JWT signing key) | Mint admin tokens; total auth bypass. |
| `terraform/envs/dev/terraform.tfstate` (and `.backup`) | Postgres `art_admin` password, `art_app` runtime password, storage account access keys (used to compute `storage_account_connection_string` even though shared-key auth is disabled at the data plane) | DB takeover. Also, although the storage account refuses shared-key auth, the keys are still embedded — if Azure ever rolled back the C2b setting somehow, the keys would work again. |

**Rules:**

- Never `cat`, `grep`, or otherwise echo the contents of these files into a chat / commit / PR description / log / screenshot.
- Verify all three are absent from `git status` output before every commit. The repo's `.gitignore` covers them, but a misconfigured `git add -A` or a renamed file could slip one in.
- Treat the `storage_account_connection_string` Terraform output as confidential even though it requires `terraform output -raw` to print — it embeds the still-existing storage account access key.
- **Future hardening:** remove the `storage_account_connection_string` output from `terraform/envs/dev/outputs.tf` once nothing in the workflow needs it. Currently kept for break-glass debugging.
- **Future hardening:** move Terraform state to a remote backend (Azure Storage with blob lease lock) — gives encryption at rest, audit trail, and per-user RBAC instead of the current "anyone with the file has all the secrets" mode.

