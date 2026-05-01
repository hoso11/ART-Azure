# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Before starting any task — read the handoff folder

The `handoff/` directory captures incident-driven rules that are not derivable from the code. Future agents must read at least the first two before proposing changes:

- **`handoff/CURRENT_STATE.md`** — current branch, Alembic head, what's implemented, what's rolled back, last verified test/build status.
- **`handoff/KNOWN_RISKS.md`** — failure modes that already cost a deployment (migration 009, poisoned `:v13` image, entrypoint whitelist semantics, Postgres enum + `varchar(32)` constraints, fragile single-in-progress invariant).
- `handoff/SAFE_TASK_RULES.md` — hard rules for DB / frontend strings / verification / operational changes.
- `handoff/NEXT_TASKS.md` — state of in-flight workstreams; what's done, what's open, what's explicitly off the roadmap.
- `handoff/ROLLBACK_NOTES.md` — what was rolled back from v13, what must not be restored, detection commands for regression.

**Hard rules:**

- Do not implement a production stage rewrite or any `009_*` migration. Production currently uses the documented safe Option B (API aggregation in `backend/app/production/service.py` — `compute_current` / `list_one_per_order` / `set_order_current`); only extend that path, and only if explicitly approved per `handoff/SAFE_TASK_RULES.md` #1. Migration `009` was deleted after a destructive deploy; the next slot is `011_*`, never `009_*`.
- Armenian UI strings must be valid Armenian Unicode only (`U+0531–U+058F`, currency `֏` U+058F). No Cyrillic / Greek / Latin lookalikes. After touching any frontend file with Armenian text, run the Cyrillic/Greek scan: `grep -rPn '[\x{0400}-\x{04FF}\x{0370}-\x{03FF}]' <files>` — zero matches required.
- Production damaged-stock uses **per-unit quantities** on `ProductionBatch` — `good_quantity`, `damaged_quantity`, `defect_reason`. Never reintroduce a whole-batch `outcome ∈ {"good","defective"}` enum, and never resurrect a `/reject` endpoint. The "all damaged" case is `{good_quantity: 0, damaged_quantity: <quantity_to_produce>}` against the existing `/complete` endpoint with strict equality `good + damaged == quantity_to_produce`.
- Damaged stock (`product_variants.damaged_stock_quantity`) must never be mixed into sellable-stock reads — catalog, order fulfillment, the `Մնացորդ` column, inventory totals, and any sellable-stock report all read `stock_quantity` only. Treating damaged units as available for sale would corrupt customer-visible inventory.
- Order-based damaged production is **Phase 2 and off the roadmap** until a product decision is made (auto-reproduce vs. mark partially fulfilled vs. ship short — see `handoff/NEXT_TASKS.md` "Open" section). Do not modify `OrderItem` or production-stage code in pursuit of damaged tracking without explicit approval.
- **All Azure resources must be deployed in `West Europe` (`westeurope`).** Single-region by design across `dev`, `int`, and `prod`. Set `var.location = "West Europe"` once per env in `terraform/envs/<env>/terraform.tfvars`; every downstream resource inherits `location` from its resource group, so do not introduce per-resource region overrides. Each environment also lives in a single resource group (`rg-art-<env>`) — do not split resources across multiple RGs without explicit approval.
  - **Exception (PostgreSQL only):** PostgreSQL Flexible Server may use a different region (default **North Europe**) **only when West Europe is blocked by an Azure subscription restriction** (`LocationIsOfferRestricted` — common on trial / Visual Studio / Azure-for-Students / MOSP subscriptions). Set `var.postgres_location` per env. The resource group, both App Service Plans, both Web Apps, and all sidecars still stay in West Europe — only `azurerm_postgresql_flexible_server.this.location` may differ. North Europe is ~10 ms from West Europe and the free 12-month B1MS offer is available there. Cross-region egress between West Europe (Web App) and North Europe (Postgres) stays inside the 100 GB always-free outbound allowance for dev workloads, so the $0 target is preserved. When the West Europe restriction is lifted (quota request approved or subscription upgraded), set `postgres_location = "West Europe"` and re-apply — the server is recreated (data loss; `pg_dump` first if there is data to keep). No other workload may use this exception.

## Critical Data Protection (load-bearing — read before any Terraform plan/apply)

**PostgreSQL Flexible Server and Azure Blob Storage Account hold all application data — every order, customer, product, audit-log row, and uploaded image. Destroying or recreating either is irreversible without a backup.** They are protected by two independent layers, both of which must remain in place by default.

### Layer 1 — Terraform `prevent_destroy = true` lifecycle blocks

Set on all four data resources in `terraform/envs/dev/main.tf`:

- `azurerm_postgresql_flexible_server.this`
- `azurerm_postgresql_flexible_server_database.app`
- `azurerm_storage_account.images`
- `azurerm_storage_container.images`

Effect: any plan that contains a destroy or replace (`-` or `-/+`) for these resources fails before apply with `Error: Instance cannot be destroyed`. Bypassing requires editing `main.tf` and removing the lifecycle line.

### Layer 2 — Azure resource locks (`CanNotDelete`)

Two locks declared in `main.tf`, scoped to the parent resource so child resources inherit:

- `azurerm_management_lock.postgres_no_delete` → scope: PostgreSQL Flexible Server (covers the database too)
- `azurerm_management_lock.storage_no_delete` → scope: Storage Account (covers the container and all blobs)

Effect: any DELETE attempt against these resources via portal, `az` CLI, ARM API, or Terraform itself returns `403 Forbidden` until the lock is removed. `CanNotDelete` allows reads and updates, so image-tag bumps, app-setting changes, container creates, blob writes, and password rotations are unaffected. Resource locks are billed under Resource Manager and are **always free**.

### Hard rules

- **Do not destroy or replace** PostgreSQL (server or database) or Azure Storage (account or container) without an explicit user approval message that names the resource.
- **Do not remove `prevent_destroy = true`** without explicit approval. The same approval should also remove the corresponding `azurerm_management_lock` if a real recreate is required.
- **Do not change `lock_level` from `CanNotDelete` to `ReadOnly`** — `ReadOnly` blocks normal updates and would break image deployments.
- **Before every `terraform apply`**, scan the plan output and report whether the protected resources are touched. The plan must show **none of**: `-/+ azurerm_postgresql_flexible_server.this`, `-/+ azurerm_postgresql_flexible_server_database.app`, `-/+ azurerm_storage_account.images`, `-/+ azurerm_storage_container.images`, `- destroy` for any of those, `-/+` or `- destroy` for the two `azurerm_management_lock` resources. Stop and surface any match.
- **Schema or data migrations** that need a non-destructive rewrite use Alembic up/down migrations or `pg_dump`/`pg_restore`, never `terraform destroy` or a `-/+` replace.
- **The documented "PostgreSQL → West Europe" recreate** when the `LocationIsOfferRestricted` block lifts is the only foreseen scenario in which `prevent_destroy` and the lock must be temporarily removed. The sequence is: `pg_dump` → comment out the lock → comment out `prevent_destroy` → apply → restore from dump → re-add `prevent_destroy` → re-add the lock → apply. Each step is its own user approval.

### Storage Account — additional non-destroy guardrails

These should also remain in place; changing them silently shifts the resource off the free tier:

- `account_replication_type = "LRS"` (GRS/ZRS bill from byte one)
- `account_kind = "StorageV2"` (premium tiers bill from byte one)
- `access_tier = "Hot"` (Cool/Archive change retrieval cost behavior)
- `allow_nested_items_to_be_public = false` (account-level safety net for the private container)

The lifecycle precondition on the Postgres server (`var.postgres_sku_name == "B_Standard_B1ms"`) is the equivalent for the database side.

## Terraform Authentication Rule (load-bearing — read before any Terraform command)

- **Do not use Azure CLI for Terraform authentication in this project.** Do not run `az login`, `az account show`, `az logout`, or any other `az …` command unless I explicitly request it.
- Terraform authenticates via a **Service Principal** whose credentials are loaded from local environment variables read out of:
  - `terraform/envs/dev/.env.terraform`
- That file contains the four `ARM_*` variables the `azurerm` provider expects: `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_SUBSCRIPTION_ID`, `ARM_TENANT_ID`.
- Before running any Terraform command, source the env file in the current shell:
  ```bash
  cd terraform/envs/dev
  source .env.terraform
  ```
  `source` only affects the current shell — re-source in a new terminal.
- `.env.terraform` is **gitignored**. Never commit it. Never echo its contents into logs, transcripts, or commit messages. If you ever see it in `git status`, stop and add it to `.gitignore` before proceeding.
- Do not replace the Service Principal flow with a personal Azure login (`az login`, `Connect-AzAccount`, OIDC) without explicit approval — those flows tie credentials to a human user instead of the project's SP and break unattended apply.
- Do not ask me to install Azure CLI for Terraform. The project does not need it.
- Run all Terraform commands from `terraform/envs/dev/`.

### Standard Terraform workflow

```bash
cd terraform/envs/dev
source .env.terraform
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

After apply, verify outputs and live URLs:

```bash
terraform output | grep -E "deployed_image|backend_image|frontend_url|backend_url"
curl -i "$(terraform output -raw backend_url)/api/v1/products/public?limit=8" | head -5
```

If Azure responds with `HTTP response was nil; connection may have been reset`, retry once with:

```bash
terraform apply -refresh=false
```

`terraform apply` requires explicit user approval each time per `handoff/SAFE_TASK_RULES.md` #14.

## Azure Free-Tier Cost Guardrails

Source of truth for what is free in Azure: **https://azure.microsoft.com/en-us/pricing/free-services#List-of-free-services**. Re-check this URL whenever you propose a new Azure resource — free-tier coverage changes and the official list is authoritative. Do not rely on memory.

### 1. Billing target

- The default target for this project is **$0 monthly Azure bill during the first 12 months**.
- Prefer only Azure services listed on the official Azure free services page above.

### 2. Allowed by default

- Only use Azure services/SKUs that are **free**, **always-free**, or **free for 12 months** according to the official page.
- Stay within the published free monthly limits.
- Use the smallest/free SKU available.
- App Service must use **F1 Free** unless I explicitly approve a paid SKU.
- Do not upgrade App Service Plan to B1, S1, P1v3, or any paid tier without my explicit approval.

### 3. Azure Free Resources Allowlist

Rules:

- Only resources in this allowlist may be proposed, created, or modified by default.
- The SKU/tier and monthly free limit must match the allowlist exactly.
- If a resource is **not** in this allowlist, it is **forbidden** unless I explicitly approve it.
- If a resource is in the allowlist but the selected SKU/tier is not free, **stop and ask** me.
- If monthly free limits can be exceeded by the proposed usage, **mention the limit before implementation**.
- If unsure, **stop and ask** before modifying Terraform.

#### Compute / Hosting

- **App Service** — Free tier **F1** only — up to 10 web/API apps, 1 GB storage, 1 hour per day — *Always free*
- **Azure Functions** — Consumption free allowance only — 1 million requests — *Always free*
- **Static Web Apps** — Free plan only — 100 GB bandwidth per subscription, 2 custom domains, 0.5 GB storage per app — *Always free*
- **Container Apps** — Free consumption allowance only — 180,000 vCPU seconds, 360,000 GiB seconds, 2 million requests — *Always free*
- **Virtual Machines Linux** — only free 12-month eligible **B2pts v2 / B2ats v2** burstable VMs — 750 hours — *12 months*
- **Virtual Machines Windows** — only free 12-month eligible **B2pts v2 / B2ats v2** burstable VMs — 750 hours — *12 months*

#### Containers

- **Azure Container Registry** — Standard tier only if included in 12-month free allowance — 1 Standard registry, 100 GB storage, 10 webhooks — *12 months*
- **Azure Kubernetes Service** — cluster management is free, but node resources are paid, so AKS is **NOT allowed by default** unless node cost is explicitly approved.

#### Databases

- **Azure Database for PostgreSQL Flexible Server** — Burstable **B1MS** only — 750 hours, 32 GB storage, 32 GB backup storage — *12 months*
- **Azure Database for MySQL Flexible Server** — Burstable **B1MS** only — 750 hours, 32 GB storage, 32 GB backup storage — *12 months*
- **Azure Cosmos DB** — free allowance only — 1,000 RU/s and 25 GB storage always-free OR 400 RU/s and 25 GB 12-month offer, depending on account eligibility
- **Azure Cosmos DB for MongoDB** — free tier / dedicated free cluster only — 32 GB storage — *Always free*
- **SQL Database** — serverless free allowance only — up to 10 databases, 100,000 vCore seconds and 32 GB storage each — *Always free*

#### Storage

- **Blob Storage** — LRS hot block blob free allowance only — 5 GB, 20,000 reads, 10,000 writes — *12 months*
- **Azure Files** — LRS free allowance only — 100 GB, 2 million operations — *12 months*
- **Archive Storage** — free allowance only — 10 GB LRS storage, 10 GB write/retrieval, 100 reads — *12 months*
- **Managed Disks** — only free allowance — 2 × 64 GB **P6 SSD**, 1 GB snapshot, 2 million I/O operations — *12 months*
- **Cloud Shell storage** — 5 GB Azure Files storage — *12 months*

#### Security / Identity

- **Key Vault** — Standard tier only — 10,000 RSA 2048-bit key or secret operations — *12 months*
- **Microsoft Entra ID** — free allowance only — 50,000 stored objects with SSO — *Always free*
- **Azure AD B2C** — free allowance only — 50,000 monthly active users — *Always free*

#### Networking

- **Bandwidth outbound** — stay within free allowance — 100 GB outbound always-free and/or 15 GB outbound 12-month offer
- **Virtual Network** — up to 50 VNets — *Always free*
- **Private Link** — free service only, but **verify private endpoint / NIC / data processing charges before using**
- **Load Balancer** — Standard Load Balancer free 12-month allowance only — 750 hours, 15 GB data processing, up to 5 rules — *12 months*
- **VPN Gateway** — **VpnGw1** only if 12-month free allowance applies — 750 hours — *12 months*
- **Network Watcher** — free allowance only — 5 GB storage, 1,000 checks, 10 tests, 10 connection metrics — *Always free*

#### Monitoring / Management

- **Cost Management** — Free — *Always free*
- **Advisor** — Free — *Always free*
- **Resource Manager** — Free — *Always free*
- **Azure Policy** — free configuration and change-tracking features only — *Always free*
- **Security Center / Defender for Cloud** — free policy assessment and recommendations only — *Always free*
- **Monitor** — only free amounts per Azure Monitor pricing; **do not enable paid ingestion / retention** without approval
- **Automation** — 500 minutes job runtime — *Always free*

#### DevOps / Developer Tools

- **Azure DevOps** — 5 users with unlimited private Git repos — *Always free*
- **Visual Studio Code** — Free — *Always free*
- **Cloud Shell** — allowed within free storage limit

#### Integration / Messaging

- **API Management** — Consumption tier only — 1 million monthly calls — *Always free*
- **Event Grid** — 100,000 operations per month — *Always free*
- **Logic Apps** — Consumption built-in actions only — 4,000 built-in actions — *Always free*
- **Service Bus** — Standard tier free allowance only — 750 hours and 13 million operations — *12 months*
- **App Configuration** — 1,000 requests per day, 10 MB storage — *Always free*
- **Notification Hubs** — 1 million push notifications with free namespace — *Always free*
- **Azure SignalR Service** — free allowance only — 20 concurrent connections per unit, 20,000 messages — *Always free*
- **Web PubSub** — free allowance only — 20,000 messages per unit per day, 20 concurrent connections, 1 unit max — *Always free*

#### AI / Cognitive Services

Only use these if the app actually needs them and the free limits are respected.

- **Azure AI Search** — 50 MB storage, 10,000 hosted documents, 3 indexes — *Always free*
- **Azure Document Intelligence** — 500 pages S0 — *12 months*
- **Azure Language** — 5,000 text records — *Always free*
- **AI Bot Service** — 10,000 premium channel messages and unlimited standard messages — *Always free*
- **AI Custom Vision** — 10,000 predictions S0, 1 training hour, 2 projects, 5,000 training images each — *12 months*
- **AI Immersive Reader** — 3 million characters — *Always free*
- **Speech to Text** — 5 audio hours per month — *Always free*
- **Text to Speech** — 0.5 million characters per month — *Always free*
- **Speech Translation** — 5 audio hours per month — *Always free*
- **Translator** — 2 million characters per month — *Always free*
- **Vision** — 5,000 transactions for S1/S2/S3 — *12 months*
- **Face** — 30,000 Free instance transactions always-free or S0 12-month allowance
- **Machine Learning** — free service only; **do not create paid compute**
- **Open Datasets** — free, but egress charges may apply
- **Content Safety** — only free allowance if applicable

#### Other allowed free services

- **Data Factory** — 5 low-frequency activities — *Always free*
- **Data Catalog** — unlimited users — *Always free*
- **Database Migration Service** — Free Standard Compute — *Always free*
- **Azure Maps** — free transaction allowance only — *Always free*
- **IoT Hub** — Free edition only — 8,000 messages per day, 0.5 KB message meter size — *Always free*
- **IoT Edge** — free open-source runtime — *Always free*
- **Azure Arc** — free control-plane functionality only — *Always free*
- **Azure Migrate** — Free — *Always free*
- **Azure Storage Mover** — Free — *Always free*
- **Azure Resource Mover** — Free, but ingress/egress charges may apply
- **Azure VM Image Builder** — free service only, but build resources / transfer may cost
- **Batch** — free orchestration only; compute may cost
- **DevTest Labs** — free service only; resources created inside may cost
- **Azure Deployment Environments** — free service only; resources deployed through it may cost
- **Azure Lighthouse** — Free
- **Azure Managed Applications Service Catalog** — free publishing
- **Azure Attestation** — Free
- **Azure Update Manager** — free for Azure resources only; Arc-enabled servers may cost

### 4. Forbidden by default

**Resources not listed in the allowlist above are forbidden by default.**

Also explicitly forbidden by default, even if they appear available in the portal:

- App Service B1 / S1 / Premium
- Application Gateway
- Azure Front Door paid tiers
- NAT Gateway
- Azure Firewall
- Paid Redis / Azure Managed Redis
- Paid Log Analytics ingestion beyond free allowance
- Paid private-endpoint-related charges unless confirmed free
- **Any paid SKU**
- **Any resource where pricing or free eligibility is uncertain**

### 5. Terraform requirements

Before adding any Azure Terraform resource:

1. Identify the exact Azure service and SKU.
2. State whether it is **free**, **12-month-free**, **always-free**, or **paid**.
3. State the monthly free limit if applicable.
4. Confirm whether it may create charges.
5. If paid or uncertain, **stop and ask** before implementing.

### 6. Cost Impact block on every Terraform change

Every proposed Terraform change must include this block in plain text **before** any code:

```
Cost Impact:
- Resource:
- SKU:
- Free category: Always free / 12 months / paid / uncertain
- Monthly free limit:
- Risk of charge:
- Keeps $0 target: yes / no / uncertain
```

If `Free category` is `paid` or `uncertain` for any resource, **stop and ask for approval before writing code.**

### 7. Safety behavior

- If unsure whether something is free, **assume it may cost money and ask first**.
- Never silently change a free SKU to a paid SKU. SKU upgrades must be called out in the proposed diff and approved before `terraform apply`.
- Never recommend paid production architecture as the next step unless clearly separated as optional future work.
- Keep Phase 1 / Phase 2 plans aligned with the $0 goal unless I explicitly approve paid services.

## Building Docker images on Windows / Git Bash (load-bearing)

The frontend production build (`frontend/Dockerfile.azure`) takes path-shaped build-args (`NEXT_PUBLIC_API_URL=/api/v1`) that are inlined into the JS bundle by webpack. **MSYS / Git Bash auto-converts arguments that start with `/` into Windows paths** before docker receives them — `/api/v1` becomes `C:/Program Files/Git/api/v1`. That string ends up in `clientFetch`'s base URL and every browser-side fetch throws `TypeError: Failed to fetch`. v22 and v23 frontend images shipped this bug; both are blacklisted in `terraform/envs/dev/variables.tf` validation.

**Rules when building from Git Bash on Windows:**

- Always set `MSYS_NO_PATHCONV=1` for the `docker build` invocation:
  ```bash
  MSYS_NO_PATHCONV=1 docker build -f frontend/Dockerfile.azure -t hoso30/art-frontend:vN \
    --build-arg "INTERNAL_API_URL=https://app-art-backend-dev-art4242.azurewebsites.net" \
    --build-arg "NEXT_PUBLIC_API_URL=/api/v1" \
    --build-arg "NEXT_PUBLIC_APP_NAME=ART Manufacturing" \
    ./frontend
  ```
- Or omit `--build-arg NEXT_PUBLIC_API_URL=/api/v1` entirely — `Dockerfile.azure` already defaults it to `"/api/v1"` (defaults written inside the Dockerfile aren't subject to MSYS conversion).
- Or run from PowerShell / cmd, which don't path-mangle.
- After every frontend image build, verify the bundle has the correct base URL before pushing:
  ```bash
  docker run --rm hoso30/art-frontend:vN sh -c \
    'find /app/.next -name "*.js" -exec grep -l "C:/Program Files/Git" {} \; 2>/dev/null'
  ```
  Empty output is required. Any match means the build is poisoned — do not push, do not bump the Terraform tag.
- Build with `--no-cache` if you suspect a poisoned base layer (relevant for any backend rebuild touching migrations, per `handoff/KNOWN_RISKS.md` #2).

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
