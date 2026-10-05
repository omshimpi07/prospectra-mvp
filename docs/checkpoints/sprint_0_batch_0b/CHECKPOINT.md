# Prospectra — Sprint 0 / Batch 0B Checkpoint

```
Project:
Prospectra

Sprint:
Sprint 0

Batch:
0B — Backend Foundation

Status:
Implementation complete, repository/environment integration pending
```

This bundle is a portable handoff artifact. The files in it are the exact Batch 0B
implementation as written and tested; nothing was rewritten or improved while packaging.
See `VERIFICATION.md` for what was and was not tested, and `MANIFEST.md` for per-file
status and SHA-256 hashes.

## Implemented

- configuration
- async SQLAlchemy database layer
- async session management
- database health helper
- declarative base
- timestamp mixin
- common API schemas
- error handling
- tests

## Files included

Source:

- `backend/config.py`
- `backend/database.py`
- `backend/models/__init__.py`
- `backend/models/base.py`
- `backend/schemas/__init__.py`
- `backend/schemas/common.py`
- `backend/middleware/__init__.py`
- `backend/middleware/errors.py`

Tests:

- `tests/backend/test_config.py`
- `tests/backend/test_database.py`
- `tests/backend/test_errors.py`

Handoff documents:

- `CHECKPOINT.md` (this file)
- `VERIFICATION.md`
- `MANIFEST.md`

Not included (outside this batch): `.gitignore` and `.env.example` from Batch 0A, `docs/`,
any `pyproject.toml`, pytest configuration, `backend/__init__.py`, `main.py`, Alembic files.

## Architectural assumptions

- Modular monolith. `backend/` is a top-level package imported as `backend.*`, with the
  repository root as the working directory / import root.
- There is deliberately no `backend/__init__.py` (it was not in the batch's file list), so
  `backend` currently resolves as a namespace package.
- Python 3.10 or later (the code uses `X | None` annotations). The user's stated target
  runtime is Windows / Python 3.14; this was not tested (see `VERIFICATION.md`).
- Database URLs use `postgresql+psycopg://`, accessed only through SQLAlchemy's async API
  (`create_async_engine`, `AsyncSession`, `async_sessionmaker`). Config rejects any other
  scheme.
- The database is Supabase PostgreSQL. Connection settings assume it may be reached through
  a transaction-mode pooler (see `prepare_threshold` below). This is an assumption and was
  not checked against a real Supabase instance.
- `.env` is read from the repository root, located relative to `backend/config.py`
  (`REPO_ROOT = parent of backend/`), not from the current working directory.
- `.env.example` from Batch 0A is the variable contract. `CORS_ORIGINS` is accepted as a
  comma-separated string (the documented format), a JSON array string, or a list.
- `SUPABASE_SERVICE_ROLE_KEY` and `GEMINI_API_KEY` are backend-only secrets. No
  frontend-facing configuration exists in this batch.
- A request-ID middleware will be added later by Antigravity. The unexpected-error handler
  already reads `request.state.request_id` if it is set and attaches it to the log record.

## Dependencies required

Not installed by this checkpoint. Required to run the code and tests:

- `fastapi` (brings `starlette` and `pydantic`)
- `pydantic-settings>=2.7` (needs `NoDecode`)
- `sqlalchemy[asyncio]` (the `asyncio` extra supplies `greenlet`; plain `sqlalchemy`
  failed on import of `sqlalchemy.ext.asyncio` in the scratch environment)
- `psycopg[binary]` (psycopg 3)
- `pytest`

Not required: `pytest-asyncio` (tests use `asyncio.run`), `httpx`, SQLite, Redis, Celery,
Docker.

Optional, used only for verification: `ruff`, `mypy`.

Exact versions used in the scratch environment are listed in `VERIFICATION.md`.

## Important design decisions

Configuration (`backend/config.py`)

- `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `GEMINI_API_KEY` are `SecretStr`, so use
  `.get_secret_value()`. `hide_input_in_errors=True` keeps rejected values out of
  validation errors.
- `DATABASE_URL` is required (no default) and must start with `postgresql+psycopg://`.
- `ENVIRONMENT` is restricted to `development`, `staging` or `production` (default
  `development`); `DEBUG` defaults to `False`; `CORS_ORIGINS` defaults to
  `["http://localhost:3000"]`; the Supabase and Gemini values default to `None`.
- `env_ignore_empty=True`: a blank value (for example a copied `.env.example`) falls back to
  the default, or counts as missing for `DATABASE_URL`. `extra="ignore"`.
- `get_settings()` is cached with `functools.lru_cache`.

Database (`backend/database.py`)

- Engine and session factory are created lazily (`lru_cache`), so importing the module
  needs no configuration.
- Pool: `pool_size=5`, `max_overflow=5`, `pool_pre_ping=True`.
- `connect_args`: `connect_timeout=10` (fail fast) and `prepare_threshold=None` (avoids
  prepared-statement problems behind a transaction-mode pooler). Both are judgment calls
  beyond the spec.
- Session factory uses `expire_on_commit=False`.
- `get_db()` yields one `AsyncSession` per call and always closes it. It never commits;
  transaction control belongs to the caller.
- `check_database_connection()` runs `SELECT 1`. It returns `False` only for
  `SQLAlchemyError` and `OSError`; other exceptions propagate. On failure it logs only the
  exception class name, because driver messages can contain host/user details.
- `dispose_engine()` closes the pool and clears the caches (intended for shutdown).

Models (`backend/models/base.py`)

- `Base` (SQLAlchemy 2.x `DeclarativeBase`) and `TimestampMixin`. No tables are declared.
- `created_at` / `updated_at` are `DateTime(timezone=True)`, non-null, set in Python via
  `utc_now()` (timezone-aware UTC) with `server_default=func.now()` for rows inserted
  outside the ORM. `updated_at` refreshes on ORM updates only (no database trigger).

Schemas (`backend/schemas/common.py`)

- `HealthResponse`: `status` is `Literal["healthy", "degraded"]`, `database` is
  `Literal["connected", "disconnected"]`, plus `timestamp` and `version="0.1.0"`. The spec
  showed `str`; `Literal` is stricter and accepts the same intended values.
- `ErrorResponse` / `ErrorDetail`: `{"error": {"code", "message", "details"}}`, where
  `details` is always an object (defaults to `{}`).

Error handling (`backend/middleware/errors.py`)

- `AppError(code, message, *, status_code=400, details=None)`.
- Handlers for application errors, request validation errors (returns only
  `loc`/`message`/`type`; never echoes submitted input), and unexpected exceptions
  (generic message to the client; traceback logged with method, path only — no query
  string — and `request_id`).
- Beyond the spec: `http_exception_handler` keeps framework errors (404, 405, ...) in the
  standard shape, and `register_error_handlers(app)` attaches all four handlers.

Tests

- Async code is tested with plain `asyncio.run`; the database tests mock the
  engine/session boundary; no real database or network is used.
- Common schema serialization tests live in `test_errors.py` because only three test files
  were in scope.

## Intentionally left for Antigravity

- Importing this code into the real repository and installing dependencies
- Python environment / virtual environment setup
- `backend` package and pytest/import configuration
- `main.py` and FastAPI application wiring (including calling `register_error_handlers`)
- Request-ID middleware and CORS middleware
- A health route using `HealthResponse` and `check_database_connection()` (none exists)
- Application shutdown wiring for `dispose_engine()`
- Alembic configuration
- Real Supabase connection verification
- Windows / Python 3.14 testing
- The Sprint 0 verification gate

## Known technical questions

Preserved as identified during implementation. None of these are resolved, and no solution
is proposed here.

1. **Windows async PostgreSQL / event-loop behavior.** As far as is known (not tested
   here), psycopg's async mode does not work with Windows' default `ProactorEventLoop`.
   Whether and how this affects the application on Windows / Python 3.14 is open.
2. **`backend` import/package configuration.** There is no `backend/__init__.py`.
   In the Linux scratch environment `python -m pytest` from the repository root worked,
   bare `pytest` failed with `ModuleNotFoundError: No module named 'backend'`, and a plain
   `mypy backend` run failed with "Source file found twice under different module names"
   (it passed with `--explicit-package-bases`).
3. **pytest configuration.** None exists (no `pythonpath`, `testpaths` or similar).
4. **Actual Supabase connection.** Only the failure path was exercised (an unreachable
   local port). The pool, `connect_timeout` and `prepare_threshold` settings are
   unverified against a real Supabase connection (direct or pooled).
5. **Final FastAPI / CORS / error middleware behavior.** As far as is known (not tested),
   Starlette runs the catch-all `Exception` handler outside user middleware, so 500 JSON
   responses may lack CORS and request-ID headers. This is untested because no CORS or
   request-ID middleware exists yet. The `http_exception_handler` addition (beyond the
   spec) also needs a decision on whether to keep it.

## Next integration step

```
Antigravity should:
1. import this implementation into the real D:\Prospectra repository
2. install the approved dependencies
3. resolve repository/package configuration
4. test on Windows/Python 3.14
5. verify the real Supabase connection
6. wire the FastAPI application
7. run the Sprint 0 verification gate
```
