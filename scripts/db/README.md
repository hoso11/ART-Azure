# PostgreSQL backup / restore helpers

Local helpers for taking a `pg_dump` of the **dev** Azure PostgreSQL Flexible
Server and restoring it into the local docker-compose Postgres for
verification.

- `dump-postgres.sh` — dump the Azure database to a local custom-format
  file under `backups/postgres/`.
- `restore-postgres-local.sh` — restore one of those dump files into the
  **local** compose Postgres only (refuses any remote target).

Both scripts use `docker run postgres:16` instead of a host-installed
`pg_dump`, so the client version always matches the server (PostgreSQL 16)
and you don't need to install anything beyond Docker.

---

## Safety warnings

- **Dumps contain every byte of the database** — orders, customers, audit
  log, hashed passwords, JWT-signed sessions in flight, everything.
  Treat any `*.dump` file as confidential.
- **Never commit dumps.** `.gitignore` covers `backups/`, `*.dump`, `*.sql`.
  Check `git status` before every commit.
- **Never paste a `*.dump` into a chat, an issue tracker, a pastebin, or
  any cloud sync folder.** It is full PII.
- **Production dumps are gated.** The dump script refuses
  `ART_DUMP_ENV=prod` unless `ART_DUMP_ALLOW_PROD=1` is also set, and the
  rule in `handoff/SAFE_TASK_RULES.md` requires explicit per-run user
  approval before that flag is used.
- **The dump script never echoes the password and never enables
  `set -x`.** Do not change those defaults.

---

## Required environment variables

The dump script reads only these variables:

| Var | Required | Default | Notes |
|---|---|---|---|
| `PGHOST`     | yes |      | Azure Postgres FQDN |
| `PGDATABASE` | yes |      | application database name |
| `PGUSER`     | yes |      | admin login (e.g. `art_admin`) |
| `PGPASSWORD` | yes |      | admin password — never on command line |
| `PGPORT`     | no  | `5432` | |
| `PGSSLMODE`  | no  | `require` | Azure requires TLS |
| `ART_DUMP_ENV` | no | `dev` | Used in the output filename. `prod` is gated. |
| `ART_DUMP_ALLOW_PROD` | no | unset | Must be `1` for any `prod` dump. |

---

## Exporting connection values from Terraform without printing secrets

Run these from the repo root in the same shell where you would normally
run Terraform. The `terraform output -raw postgres_admin_password` call
expands the password into the shell variable directly — it is **never
printed** to the terminal.

```bash
# Service-Principal creds for Terraform (you already do this for plan/apply)
source terraform/envs/dev/.env.terraform

# Connection values (non-sensitive)
export PGHOST="$(terraform -chdir=terraform/envs/dev output -raw postgres_fqdn)"
export PGDATABASE="$(terraform -chdir=terraform/envs/dev output -raw postgres_database)"
export PGUSER="$(terraform -chdir=terraform/envs/dev output -raw postgres_admin_user)"

# Password (sensitive — captured into env, not echoed)
export PGPASSWORD="$(terraform -chdir=terraform/envs/dev output -raw postgres_admin_password)"
```

To verify the variables are set without leaking the password:

```bash
echo "PGHOST=${PGHOST}"
echo "PGDATABASE=${PGDATABASE}"
echo "PGUSER=${PGUSER}"
echo "PGPASSWORD is set: $([ -n "${PGPASSWORD:-}" ] && echo yes || echo no)"
```

---

## Run a dump

```bash
./scripts/db/dump-postgres.sh
```

Output:

```
backups/postgres/art-dev-postgres-2026-05-04-1530.dump
```

The script prints environment, host, database, user, output path, and
post-success file size. The dump file format is `pg_dump -Fc` (custom),
which is binary, compressed, and consumed by `pg_restore`.

When you are done, optionally clear the password from the current shell:

```bash
unset PGPASSWORD
```

---

## Restore locally for verification

The restore script targets only the local compose Postgres and refuses
any remote host. It creates a fresh `art_local_restore` database
(separate from the running app's `art_manufacturing`) so a restore can
never clobber your local dev data.

```bash
# 1. Local stack must be up
make up

# 2. Restore (pass the dump path)
./scripts/db/restore-postgres-local.sh backups/postgres/art-dev-postgres-2026-05-04-1530.dump

# 3. Connect from the host
psql -h localhost -p 5432 -U art_user -d art_local_restore   # password: art_password
```

If your compose project name is not `art-azure-terraform` (the lowercased
repo directory), set `COMPOSE_PROJECT=<name>` before running the restore
script. The script joins the `<project>_default` network.

---

## Docker requirement

Both scripts run `docker run --rm postgres:16 …`. Docker Desktop (or any
Docker daemon on Linux) must be installed and running. No host-side
PostgreSQL install is required.

---

## Firewall — temporary rule for your public IP

Azure PostgreSQL Flexible Server in this environment has
`public_network_access_enabled = true`, but the only standing firewall
rule is `AllowAzureServices` — that opens the Azure backbone only and
does **not** cover home/office IPs. A `pg_dump` from your laptop will
therefore time out until your current public IP is added.

We add the rule through Terraform (never `az`), via the optional
`dump_client_ip` variable. The rule lives in `main.tf` as
`azurerm_postgresql_flexible_server_firewall_rule.dump_client` with
`count = var.dump_client_ip == null ? 0 : 1`, so when the variable is
unset there is **zero** drift.

### Add the rule, dump, remove the rule

```bash
# 1. Find your current public IP (no secrets in this command)
curl -s https://api.ipify.org && echo

# 2. Open gitignored terraform.tfvars and add the line:
#       dump_client_ip = "<that IP>"
#    Save and close. Do NOT commit terraform.tfvars (it is gitignored).
$EDITOR terraform/envs/dev/terraform.tfvars

# 3. Plan — expect "1 to add" (the DumpClient rule). Verify the protected
#    resources are NOT in the plan (per CLAUDE.md "Critical Data Protection").
cd terraform/envs/dev
source .env.terraform
terraform plan -out=tfplan

# 4. Apply (requires explicit user approval per SAFE_TASK_RULES #19).
terraform apply tfplan

# 5. Run the dump (back at repo root).
cd -
./scripts/db/dump-postgres.sh

# 6. Remove the rule. Either delete the `dump_client_ip` line from
#    terraform.tfvars or set it to null.
$EDITOR terraform/envs/dev/terraform.tfvars

# 7. Plan + apply again — expect "1 to destroy" (DumpClient).
cd terraform/envs/dev
terraform plan -out=tfplan
terraform apply tfplan
```

### Rules

- **Always remove the rule after dumping.** A `DumpClient` rule left in
  place exposes 5432 to that single IP indefinitely. Even though the
  data plane still requires `art_admin` credentials, an unused open
  port is unnecessary attack surface.
- **`dump_client_ip` is a single IPv4 address only.** Variable-level
  validation rejects CIDR ranges and any non-IPv4 input. If your ISP
  rotates your public IP, your existing rule will silently stop working
  — re-run step 1.
- **Never commit a real IP.** `terraform.tfvars` is gitignored;
  `terraform.tfvars.example` only documents the variable. Verify with
  `git status` before every commit.

### Alternative: Kudu SSH inside the backend Web App

If you cannot or do not want to add a firewall rule, you can run the
dump from inside the backend Web App's Kudu SSH
(`https://app-art-backend-dev-<suffix>.scm.azurewebsites.net/webssh/host`).
The Web App is already inside the Azure backbone, so
`AllowAzureServices` covers it. The trade-offs are: the postgres-client
package is not in the image and would have to be installed each session,
extracting the dump file is awkward, and the action leaves no record in
`terraform plan`. Use only as a fallback.

The dump script's "connection failed" error message points back to this
section so future runs without the firewall do not look like a generic
network failure.

---

## Production warning

```
ART_DUMP_ENV=prod              # required to even attempt a prod dump
ART_DUMP_ALLOW_PROD=1          # required to bypass the dump-script gate
```

Even with both set, **a production dump still requires explicit per-run
user approval** per `handoff/SAFE_TASK_RULES.md`. The dump file is full
production PII; it must not leave the operator's machine, must not be
committed, must not be uploaded to any external service, and should be
deleted immediately after the verification it was taken for.

---

## Files

- `scripts/db/dump-postgres.sh`
- `scripts/db/restore-postgres-local.sh`
- `scripts/db/README.md` *(this file)*

Output directory: `backups/postgres/` (created on first run; gitignored).
