# Safe Task Rules

Hard rules for any future change in this repo. These exist because each one corresponds to an incident or near-miss already paid for in production.

## Database

1. **No new Alembic migration without explicit user approval.** State the plan first: which tables, which columns, the revision id (≤ 32 chars), the down-revision, the up/downgrade SQL, and how it behaves on Postgres (not just SQLite). Wait for "yes" before generating the file.
2. **No destructive SQL in or out of migrations.** No `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, mass `DELETE`, or `UPDATE` without a `WHERE`. If the user asks for one, restate what will be lost and ask again.
3. **No enum rename, drop, or value reordering on `stagename` / `stagestatus`** (or any other Postgres enum). These are the exact failure mode that broke migration 009. If a value must change, propose a parallel column + backfill + cutover migration over multiple revisions, not an in-place enum alter.
4. **New revision id must be added to the entrypoint whitelist** in `backend/entrypoint.sh` in the same commit as the migration file. Otherwise the boot guard will silently downgrade fresh databases.
5. **Test new migrations against Postgres**, not just SQLite. `make up` then `make migrate` against a clean volume reproduces production behavior; `make test` does not.

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

### Service Principal role for Terraform — Contributor by default, Owner only when changing locks

The SP that authenticates Terraform (`ARM_CLIENT_ID` from `terraform/envs/dev/.env.terraform`) holds **Contributor** at subscription scope by default. That is sufficient for **all day-to-day Terraform operations**:

- bumping `frontend_image_tag` / `backend_image_tag`
- editing `app_settings` on either Web App
- adding/removing Postgres firewall rules
- rotating the Postgres admin password (`random_password.postgres_admin` regen)
- reading the existing locks (`terraform plan` refresh)
- creating new resources inside `rg-art-dev` from the free-tier allowlist

Contributor **does NOT** include `Microsoft.Authorization/locks/*`, so it cannot create, modify, or remove `azurerm_management_lock` resources. Apply will fail with `403 AuthorizationFailed` on any lock mutation.

**When Owner (or an equivalent narrow custom role with `Microsoft.Authorization/locks/*`) is required:**

- Adding a new `azurerm_management_lock` to any resource.
- Modifying a lock's `notes`, `lock_level`, `name`, or `scope`.
- Removing a lock (e.g. step 2 of the "PostgreSQL → West Europe" recreate procedure above).
- The first-time creation of `postgres_no_delete` and `storage_no_delete` (already done; not relevant unless they need to be recreated).

**Procedure when lock changes are needed:**

1. Portal → Subscription → Access control (IAM) → grant the SP **Owner** at subscription scope (or grant a narrower custom role with `Microsoft.Authorization/locks/read,write,delete`). Wait ~1 min for propagation.
2. Run the Terraform change.
3. Portal → IAM → revoke the elevated role, leaving the SP back at Contributor only.

The locks already in Azure remain protective regardless of what role the SP holds — they're stored ARM resources, independent of the credential that created them. The running app is also unaffected by the SP's role (backend uses Postgres password + `AZURE_STORAGE_CONNECTION_STRING`, neither of which depends on RBAC).

Document any role elevation event in the handoff folder so future agents know it happened.

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
