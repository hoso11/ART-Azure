# Backend tests

Pytest + httpx ASGI client. SQLite-backed (`sqlite+aiosqlite:///./test.db`) via
`dependency_overrides[get_db]` — Postgres is never touched.

## Layout

```
backend/tests/
├── conftest.py           shared fixtures: client, admin_user, customer,
│                         simple_user, admin_cookies, user_cookies, db_session,
│                         setup_db (autouse: creates+drops schema per test)
├── test_auth.py          authentication / token flows
├── test_products.py      products + variants + size-material requirements
├── test_inventory.py     materials, inventory, stock movements
├── test_orders.py        order CRUD + status transitions + RBAC
└── test_fulfillment.py   stock-first order fulfillment matrix
```

One file per domain. Group fixtures in `conftest.py`. Reach for a small
`_helper()` function inside the test file when several tests need the same
multi-step setup (see `test_fulfillment.py` for the pattern).

## Running

```bash
# All tests
make test
# or:  docker-compose exec backend pytest tests/ -v

# Single file
docker-compose exec backend pytest tests/test_fulfillment.py -v

# Single test
docker-compose exec backend pytest tests/test_orders.py::test_create_order -v

# Stop on first failure
docker-compose exec backend pytest tests/ -x
```

## Adding a test for a new feature

1. Pick the existing `test_<domain>.py` file or create a new one if the feature
   is a new domain.
2. Use the existing fixtures from `conftest.py` (`client`, `admin_cookies`, etc.)
   instead of building auth from scratch.
3. Hit the real HTTP route — don't import service functions directly. The route
   is the contract.
4. Assert on the **observable outcome** (response body, DB row read back via
   another GET), not on internal call counts.
5. Run the full suite before declaring done: `make test` must be green.

Each test gets a fresh schema (the `setup_db` autouse fixture in
`conftest.py:26` creates and drops every table per test), so tests are
order-independent and safe to run in parallel.
