# Safe Task Rules

Hard rules for any future change in this repo. These exist because each one corresponds to an incident or near-miss already paid for in production.

## Database

1. **No new Alembic migration without explicit user approval.** State the plan first: which tables, which columns, the revision id (≤ 32 chars), the down-revision, the up/downgrade SQL, and how it behaves on Postgres (not just SQLite). Wait for "yes" before generating the file.
2. **No destructive SQL in or out of migrations.** No `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, mass `DELETE`, or `UPDATE` without a `WHERE`. If the user asks for one, restate what will be lost and ask again.
3. **No enum rename, drop, or value reordering on `stagename` / `stagestatus`** (or any other Postgres enum). These are the exact failure mode that broke migration 009. If a value must change, propose a parallel column + backfill + cutover migration over multiple revisions, not an in-place enum alter.
4. **New revision id must be added to the entrypoint whitelist** in `backend/entrypoint.sh` in the same commit as the migration file. Otherwise the boot guard will silently downgrade fresh databases.
5. **Test new migrations against Postgres**, not just SQLite. `make up` then `make migrate` against a clean volume reproduces production behavior; `make test` does not.
5a. **Application runtime uses `art_app` (CRUD only, Task C1).** `art_admin` is reserved for Alembic + `scripts/bootstrap_db_user.py` which run from `backend/entrypoint.sh` before uvicorn starts. Do **not** wire app code (FastAPI handlers, services, Celery tasks) to `DATABASE_URL_SYNC` or any other admin-credentialed DSN. New mutations + new tables must remain accessible to `art_app` via the existing grants — `bootstrap_db_user.py` runs `GRANT … ON ALL TABLES/SEQUENCES … IN SCHEMA public` and `ALTER DEFAULT PRIVILEGES`, so newly-created objects inherit access automatically. If a future feature genuinely needs DDL at runtime (rare — almost always belongs in an Alembic migration instead), state the case in writing and get explicit approval before granting `art_app` more privileges or before reverting to admin DSNs.
5b. **Do not edit `backend/scripts/bootstrap_db_user.py` to skip the gate, hardcode a password, or introduce string-formatted SQL.** The script uses `psycopg2.sql.Identifier` / `psycopg2.sql.Literal` to compose every `CREATE ROLE` / `ALTER ROLE` / `GRANT` / `REVOKE` statement; reverting to `f"CREATE ROLE {user}"` opens SQL injection on the password field. Tests in `backend/tests/test_db_bootstrap.py` lock down the role name (`art_app`), the password validator, and the absence of hardcoded password literals — keep them green.

## Frontend strings

6. **No hardcoded Armenian translation maps for product/category/description data unless explicitly approved.** If the API returns the value, render it directly — do not translate in the frontend. The homepage `FeaturedProducts.tsx` cleanup in commit `ef49b8d` removed the last such map; do not reintroduce the pattern in a new component.
7. **All Armenian text uses Unicode `U+0531–U+058F` only.** No Cyrillic / Greek lookalikes (CLAUDE.md "Armenian UI text rules" is load-bearing — re-read it before any frontend text change).
8. **Run the Cyrillic/Greek scan** on every modified frontend file before declaring done:
   ```
   grep -rPn '[\x{0400}-\x{04FF}\x{0370}-\x{03FF}]' <files>
   ```
   Zero matches required.

## Verification (every task)

9. **Run `make test` (`docker-compose exec backend pytest tests/ -q`) and confirm `N passed, 0 failed`.** New feature → new test. Failing tests are not "I'll fix in the next PR".
10. **Run `docker-compose exec frontend npx tsc --noEmit`** for any frontend change; exit 0 required.
11. **Run `docker-compose exec frontend npm run build`** for any non-trivial frontend change; "Compiled successfully" required.
12. **Audit logging** on every new mutation endpoint (`activity_service.log_activity(...)`). See CLAUDE.md "Definition of done" #5 for the exact pattern.
13. If you can't run a check (Docker is down, etc.), say so explicitly. Never silently skip and report success.

## Operational

14. **Do not push, merge, force-push, or rebase published branches** without explicit approval each time. A single "yes, commit" does not authorize a push.
15. **Do not pull, tag, or publish the `hoso30/art-backend:v13` Docker image.** It contains the failed migration 009. Always build from the current commit with `--no-cache`.
16. **Do not edit `backend/entrypoint.sh` migration-guard logic** beyond extending the whitelist. The retry loop, the silent-rewrite-to-006 fallback, and the SQL itself are load-bearing for already-deployed databases. Larger changes need a discussion of every DB currently in the wild.
17. **Do not delete or rename existing migration files.** If a revision must be retired, the retirement plan is its own task and must include a story for every database currently stamped at that revision.
17a. **Sensitive files — never commit, never echo:**
   - `terraform/envs/dev/.env.terraform` — Service Principal credentials. Subscription-level access.
   - `terraform/envs/dev/terraform.tfvars` — `backend_secret_key` (JWT key) + `enable_storage_role_assignment`.
   - `terraform/envs/dev/terraform.tfstate` (and `.backup`) — Postgres admin password, `art_app` runtime password, storage account access keys (still embedded in state even with `shared_access_key_enabled = false`).

   All three are gitignored. If any appears in `git status`, stop and verify `.gitignore` before any commit. Never `cat` their contents into a chat, commit message, or log. The `storage_account_connection_string` Terraform output is marked `sensitive` — treat as confidential even though shared-key auth is disabled at the data plane. **Future hardening:** remove the `storage_account_connection_string` output entirely if no workflow needs it.

## RBAC — five-role authorization matrix (v35 / v32)

17e. **Backend RBAC is authoritative.** Every API endpoint that mutates or returns non-public data is gated by `Depends(require_roles(*GROUP))` (or a tighter custom dependency in `users/router.py`). Frontend hiding via `MODULE_ACCESS` / `ROLE_LABELS` in `frontend/src/lib/permissions.ts` is **UX-only** — it shapes the sidebar and prevents broken pages, but it does not enforce authorization. New endpoints must:
   - Pick the right role group from `backend/app/dependencies.py` (`ADMIN_ONLY`, `USER_MANAGEMENT`, `BUSINESS_MANAGER`, `INVENTORY_MANAGER`, `PRODUCTION_INVENTORY_READ`, `CUSTOMER_MANAGEMENT`, `REPORT_MANAGEMENT`, `PRODUCTION_REPORTS`, `ACTIVITY_VIEW`, `ORDERS_VIEW`, `PRODUCTS_VIEW`) and use `Depends(require_roles(*GROUP))`. Do not invent a new ad-hoc check.
   - For any new role group constant: update `backend/app/dependencies.py`, mirror the change in `frontend/src/lib/permissions.ts` `MODULE_ACCESS`, and add a parametrized test row to `backend/tests/test_authorization_matrix.py`.
   - For new mutation endpoints, audit logging still applies (CLAUDE.md "Definition of done" #5).
17f. **Director cannot create or update non-`simple_user` accounts.** The service helper `can_assign_role(actor, target_role)` in `backend/app/users/service.py` returns `True` only for `(admin, *)` and `(director, simple_user)`; `can_manage_user(actor, target)` returns `True` only when `actor.role == admin` or `target.role == simple_user`. Director's `GET /users` is filtered server-side via `service.list_users(..., restrict_to_role=UserRole.simple_user)`. **Do not bypass these helpers** in new code — call them from the route guard, not duplicate the logic. Mirror the rule in the frontend via `allowedRolesFor(actor)`.
17g. **Self-role-change and self-deactivation are blocked.** PATCH `users/{id}` rejects role changes when `target.id == actor.id` (`self_role_change_denied` 403); DELETE / PATCH `is_active=false` on the actor's own account returns `self_deactivation_denied` 403. **Do not "fix" these guards** to support a "demote yourself before you leave" workflow — separate the two operations: another admin must perform the change.
17h. **Last-active-admin protection must remain in place.** PATCH or DELETE that would leave zero active admins returns `last_admin_required` 422. The helper is `service.is_last_active_admin(db, user)`. Do not loosen the predicate (e.g. counting deactivated admins) without explicit approval.
17i. **`UserRole` ENUM is forward-only.** The Postgres `userrole` ENUM was extended in `012_extend_user_roles` with `director`, `production_manager`, `warehouse_manager`. Postgres does not support `ALTER TYPE … DROP VALUE`. **Do not propose a "downgrade" migration that removes the new values.** A rollback to a pre-v35 backend image is conditional — see `handoff/ROLLBACK_NOTES.md` "RBAC ENUM extension is forward-only" and `KNOWN_RISKS.md` #14.

## Storage / Managed Identity (Tasks C2a + C2b)

17b. **The backend's Storage Managed Identity is the only blob auth path. Do not undo it.** Specifically:
- Do not remove `identity { type = "SystemAssigned" }` from `azurerm_linux_web_app.backend`.
- Do not delete `azurerm_role_assignment.backend_blob_data_contributor[0]` or change its `role_definition_name` to a weaker role.
- Do not flip `azurerm_storage_account.images.shared_access_key_enabled` back to `true` for any reason except a documented break-glass operation (e.g. running `azcopy` from a workstation), and only with explicit user approval; flip back to `false` immediately after.
- Do not re-add `AZURE_STORAGE_CONNECTION_STRING` to backend `app_settings`. The adapter prefers MI when `AZURE_STORAGE_ACCOUNT_URL` is set, but leaving the connection string in `app_settings` re-introduces a credential surface and is a regression even if the data plane refuses it.
17c. **Do not change `enable_storage_role_assignment` from `true` to `false`** in the dev `terraform.tfvars`. That would plan a destroy of the role assignment, breaking the running backend's blob auth. The `false` default in `variables.tf` is for the bootstrap-on-existing-Web-App workaround and applies to greenfield envs only.
17d. **Do not remove `storage_use_azuread = true`** from `provider "azurerm"` in `providers.tf` while `shared_access_key_enabled = false`. The pairing is required — see `handoff/KNOWN_RISKS.md` "storage_use_azuread + shared-key disabled".

## Critical Data Protection (PostgreSQL + Azure Blob Storage)

**These resources hold application data. Their destruction is irreversible without backups. Both Terraform-side and Azure-side guards are in place; do not weaken either.**

Protected resources:

- `azurerm_postgresql_flexible_server.this` (server)
- `azurerm_postgresql_flexible_server_database.app` (`art_manufacturing` DB)
- `azurerm_storage_account.images` (`startdevimgsart4242`)
- `azurerm_storage_container.images` (`art-images`)

24. **Never destroy or replace any of the four protected resources without explicit user approval naming the resource.** That approval is required separately even if `terraform plan` happens to show a destroy/replace as a side effect of an unrelated change.
25. **Do not remove `prevent_destroy = true`** from any of the four lifecycle blocks. A removal is its own approved task that must include the recovery story (`pg_dump` for Postgres, blob copy for Storage).
26. **Do not remove or modify the two `azurerm_management_lock` resources** (`postgres_no_delete`, `storage_no_delete`) without explicit user approval. They're free (Resource Manager) and are the Azure-side defense against accidental portal/CLI deletes.
27. **Do not change `lock_level` from `CanNotDelete` to `ReadOnly`.** `ReadOnly` blocks normal updates and would break every Terraform plan that touches an app setting or image tag.
28. **Pre-apply scan** is mandatory. Before `terraform apply`, parse the plan output and report explicitly whether any of these strings appear:
    - `-/+ azurerm_postgresql_flexible_server.this`
    - `-/+ azurerm_postgresql_flexible_server_database.app`
    - `-/+ azurerm_storage_account.images`
    - `-/+ azurerm_storage_container.images`
    - `-/+ azurerm_management_lock.postgres_no_delete`
    - `-/+ azurerm_management_lock.storage_no_delete`
    - `- destroy` followed by any of the resource names above

    If **any** match → STOP and surface to the user. Do not apply.
29. **Prefer safe migration over destroy/recreate.** Schema changes go through Alembic up/down migrations. Data moves go through `pg_dump`/`pg_restore` or `azcopy`. The `terraform destroy` / `-/+` replace path is reserved for the documented "PostgreSQL → West Europe" recreate when the subscription block lifts, and only after `pg_dump` has succeeded.

The "Postgres → West Europe" recreate sequence (only foreseen scenario for legitimate destroy):

1. `pg_dump` of `art_manufacturing` to a local file. Verify the dump is non-zero and re-importable.
2. Comment out `azurerm_management_lock.postgres_no_delete`.
3. Comment out `prevent_destroy = true` on `azurerm_postgresql_flexible_server.this` and `azurerm_postgresql_flexible_server_database.app`.
4. `terraform apply` — server is recreated in West Europe.
5. `pg_restore` from the dump.
6. Restore the two lifecycle lines and the lock resource. `terraform apply`.

Each step is its own user approval; "go ahead with the migration" does not extend to all of them.

### Service Principal role for Terraform — current state and downgrade requirements

The SP that authenticates Terraform (`ARM_CLIENT_ID` from `terraform/envs/dev/.env.terraform`) currently holds **Owner** at subscription scope. The elevation history:

1. **Originally** Contributor — sufficient for steady-state Phase 1–4 operations.
2. **Elevated to Owner during Task C2a** to grant itself permission to create the `Storage Blob Data Contributor` role assignment (`Microsoft.Authorization/roleAssignments/write`).
3. **Retained as Owner after Task C2b** because `provider "azurerm" { storage_use_azuread = true }` in `providers.tf` requires the SP to have a Storage data-plane role on `azurerm_storage_account.images` to read sub-properties (`queue_properties`, etc.) on every plan. Owner satisfies this transitively.

**Downgrading the SP back to Contributor — what breaks and how to keep things working:**

Day-to-day Terraform operations that work as Contributor:

- bumping `frontend_image_tag` / `backend_image_tag` (sidecar image fields)
- editing `app_settings` on either Web App
- adding/removing Postgres firewall rules
- rotating the Postgres admin password and the `art_app` runtime password
- creating new resources inside `rg-art-dev` from the free-tier allowlist

What breaks if the SP loses Owner without a replacement Storage data-plane role:

- Every `terraform plan` 403s on `KeyBasedAuthenticationNotPermitted` while the provider tries to read storage account `queue_properties` / `share_properties` / `static_website` / `blob_properties` via shared keys (which are disabled). See `handoff/KNOWN_RISKS.md` "storage_use_azuread + SP downgrade".
- All apply paths are blocked because plan can't complete.

**To downgrade safely:**

1. Portal → Storage account `startdevimgsart4242` → Access control (IAM) → grant the SP **`Storage Blob Data Owner`** (or `Storage Blob Data Contributor`) at the storage account scope. This survives Owner revocation.
2. Wait ~1 min for propagation; verify with a `terraform plan` (should return clean).
3. Portal → Subscription → IAM → revoke Owner, leaving Contributor + the explicit storage role.

**When Owner (or an equivalent narrow custom role with the right permissions) is required again:**

- Adding a new `azurerm_management_lock` to any resource (`Microsoft.Authorization/locks/*`).
- Modifying a lock's `notes`, `lock_level`, `name`, or `scope`.
- Removing a lock (e.g. step 2 of the "PostgreSQL → West Europe" recreate procedure above).
- Creating, deleting, or modifying `azurerm_role_assignment` resources (`Microsoft.Authorization/roleAssignments/*`). The C2a role assignment is already in place; recreation would only be needed if Terraform state for it were lost.

**Procedure when these changes are needed:**

1. Portal → Subscription → Access control (IAM) → grant the SP **Owner** (or a narrower custom role with the required permissions). Wait ~1 min.
2. Run the Terraform change.
3. Portal → IAM → revoke Owner. Verify Contributor + Storage Blob Data Owner remain.

The locks and role assignments already in Azure remain protective regardless of what role the SP holds — they're stored ARM resources, independent of the credential that created them. The running app is also unaffected by the SP's role:

- Postgres: backend authenticates as `art_app` with the runtime password (`random_password.art_app_db.result`) — independent of any Azure RBAC.
- Blob Storage: backend authenticates via System-Assigned MI's bearer token + the existing `Storage Blob Data Contributor` role assignment — independent of the SP.

**Document any role elevation event in this section so future agents know it happened.** The current state (Owner since C2a, retained for storage_use_azuread reads) should be reviewed periodically; if the storage data-plane role is granted explicitly, downgrade Owner and update this doc.

## Terraform / deployment

18. **Do not use Azure CLI for Terraform authentication.** No `az login`, `az account show`, etc. Terraform reads the SP credentials from `terraform/envs/dev/.env.terraform` — `source` it before running any Terraform command. See CLAUDE.md "Terraform Authentication Rule".
19. **`terraform apply` requires explicit user approval each time.** The full sequence is `source .env.terraform && terraform plan -out=tfplan && <wait for user approval> && terraform apply tfplan`. A previous "yes" does not extend.
20. **Frontend production images must be built from `frontend/Dockerfile.azure`**, never `frontend/Dockerfile` (the dev image). v21 was built wrong and crashed in Azure with a Tailwind PostCSS error. See `KNOWN_RISKS.md` #9.
21. **Building frontend images from Git Bash on Windows requires `MSYS_NO_PATHCONV=1`.** Otherwise MSYS rewrites `--build-arg NEXT_PUBLIC_API_URL=/api/v1` into `C:/Program Files/Git/api/v1` and every browser-side fetch in the resulting bundle throws `TypeError`. v22 and v23 shipped this bug. See `KNOWN_RISKS.md` #8.
22. **Verify frontend image is clean before pushing**:
    ```bash
    docker run --rm hoso30/art-frontend:vN sh -c \
      'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'
    ```
    Empty output required. If anything matches, do not push and do not bump the Terraform tag.
23. **Image tags `v13` (backend), `v21`/`v22`/`v23` (frontend) are blacklisted in `terraform/envs/dev/variables.tf` validation.** Do not remove them from the blacklist. If a future tag is found to be poisoned, add it to the blacklist immediately rather than relying on humans to remember.

## When in doubt

18. **Stop and ask.** "I'm not sure whether X is safe — should I proceed?" is always cheaper than rolling back a deployment. The user has explicitly preferred this over a confident wrong action multiple times.
