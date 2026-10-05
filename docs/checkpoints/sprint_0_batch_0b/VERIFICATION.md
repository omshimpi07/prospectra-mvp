# Prospectra — Sprint 0 / Batch 0B Verification Report

This report separates what was actually executed from what was not. Nothing listed under
"Not yet verified" should be treated as working.

## Environment used

All testing was performed in a **Linux / Python 3.12.3 scratch environment** (a throwaway
virtual environment in a sandbox), **not** in the actual Windows / Python 3.14
`D:\Prospectra` repository. **Nothing here has been verified on Windows.**

Package versions in the scratch environment:

```
Python             3.12.3
fastapi            0.142.2
starlette          1.7.0
pydantic           2.13.5
pydantic_core      2.46.5
pydantic-settings  2.15.0
SQLAlchemy         2.1.3
greenlet           3.5.6
psycopg            3.3.6
psycopg-binary     3.3.6
pytest             9.1.1
ruff               0.16.10
mypy               2.4.0
httpx              0.28.1   (installed only for one ad-hoc check below; not needed by the tests)
```

The tests were run from a copy of the repository layout (`backend/` and `tests/`) so that
no caches or bytecode were written next to the deliverables.

## Verified

### Test suite

- Command: `python -m pytest tests/backend -q` from the repository root
- Result: **48 tests passed**, 0 failed
  (`test_config.py` 17, `test_database.py` 14, `test_errors.py` 17)
- Also passed when the files were run in a different order
  (`test_errors`, `test_database`, `test_config`), which checks test isolation.

### ruff result

- Command: `ruff check backend tests` (default rules, no project configuration)
- Result: `All checks passed!`

### mypy result

- Command: `mypy --explicit-package-bases backend`
- Result: `Success: no issues found in 8 source files`
- Note: plain `mypy backend` (without `--explicit-package-bases`) failed with "Source file
  found twice under different module names". This is the package-configuration question
  listed below, not a type error.

### Configuration behavior (covered by `test_config.py`)

- Development defaults (`development`, `DEBUG=False`, default CORS origin, optional
  Supabase/Gemini values `None`)
- Environment overrides for every setting; secrets readable via `get_secret_value()`
- Invalid `ENVIRONMENT` value rejected
- `DATABASE_URL` required; a blank `DATABASE_URL` counts as missing
- Blank optional values fall back to defaults
- `DATABASE_URL` must use `postgresql+psycopg://` (`postgresql://`, `postgresql+asyncpg://`
  and `mysql://` rejected), and the rejected value's password does not appear in the error
- `CORS_ORIGINS` parsed to `list[str]` from a single origin, comma-separated values
  (including stray spaces and a trailing comma), and a JSON array string; malformed JSON
  rejected
- Secrets do not appear in `repr()` / `str()` of the settings object
- `.env` file loading (temporary file), with unknown keys ignored
- `get_settings()` caching and `cache_clear()`
- Ad-hoc check (not part of the test suite): `Settings` loaded from the actual Batch 0A
  `.env.example` produced the expected values, with `CORS_ORIGINS` as a `list`

### Mocked database behavior (covered by `test_database.py`)

No real database or network connection was used in the suite.

- Engine construction (without connecting): driver `postgresql+psycopg`, async dialect,
  pool size 5, cached instance
- Session factory: `AsyncSession` class, `expire_on_commit=False`, cached instance
- `get_db()`: yields the session and closes it afterwards; closes it when the request fails
  (exception thrown into the generator); yields a real `AsyncSession` without connecting
- `check_database_connection()`: success path executes `SELECT 1` and returns `True`;
  failure path (`OperationalError`, `OSError`) returns `False` and the log contains the
  exception class name but not host, user, password or the database URL; an unexpected
  exception type (`ValueError`) propagates
- Declarative base: `Base` declares no tables; `utc_now()` is timezone-aware UTC;
  `created_at` / `updated_at` are timezone-aware, non-null, with Python and server
  defaults; `updated_at` has an `onupdate`, `created_at` does not
- Ad-hoc check (not part of the test suite): a real, unmocked connection attempt to an
  unreachable local port (`127.0.0.1:1`) returned `False`, and the log contained only
  `OperationalError` with no credentials or host

### Error formatting behavior (covered by `test_errors.py`)

- `AppError` produces the standard `{"error": {"code", "message", "details"}}` body with its
  status code (default 400, default empty `details`)
- Validation errors return 422, code `VALIDATION_ERROR`, entries containing only
  `loc` / `message` / `type`; submitted input is not echoed
- HTTP exceptions (404, 401 with preserved headers, structured detail, unknown status code)
  use the standard shape
- Unexpected exceptions return 500 with a generic message and no exception text, class
  name or traceback in the body; the traceback is logged with the request path and
  `request_id` (or `None`)
- `register_error_handlers` registers all four handlers on a `FastAPI` instance
- Response schema serialization: `ErrorResponse`, `ErrorDetail`, `HealthResponse` (default
  version `0.1.0`, UTC timestamp serialization, unintended `status`/`database` values
  rejected)
- Ad-hoc check (not part of the test suite): a minimal `FastAPI` app with
  `register_error_handlers`, driven through `TestClient` (needs `httpx`), returned the
  standard shape for a 409 `AppError`, a 404, a 405, a 422 and a 500

### Issues found and fixed during verification (before this checkpoint)

The files in this bundle are the post-fix versions.

- Plain `sqlalchemy` lacked `greenlet`; `sqlalchemy[asyncio]` is required.
- A test fixture called `cache_clear()` on module attributes that other tests had
  monkeypatched with plain functions; fixed in `test_database.py`.
- mypy reported a `dict` vs `Mapping` type mismatch for response headers; fixed in
  `backend/middleware/errors.py`.

## Not yet verified

None of the following has been tested. Do not treat any of them as working.

- Windows Python 3.14 runtime
- actual Prospectra repository integration (`D:\Prospectra`)
- actual Supabase PostgreSQL `SELECT 1`
- actual Alembic integration
- FastAPI application wiring
- Windows async event-loop behavior
- final pytest import/package configuration
- CORS + request ID behavior after `main.py` integration

Also not checked: whether the pinned/required packages (for example `psycopg[binary]`)
install and run on Windows / Python 3.14; behavior of `.env` loading on Windows paths; and
a successful (non-failing) connection of any kind.

## Checkpoint creation

No application code was changed while creating this checkpoint. Before packaging, the
source and test files were compared byte-for-byte with the copy that produced the results
above and were identical; their SHA-256 hashes are recorded in `MANIFEST.md`.
