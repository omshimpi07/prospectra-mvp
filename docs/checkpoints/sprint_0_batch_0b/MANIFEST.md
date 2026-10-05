# Manifest — Prospectra Sprint 0 / Batch 0B Checkpoint

| File path | Purpose | Status | SHA-256 |
|---|---|---|---|
| `backend/config.py` | Typed settings (pydantic-settings), CORS parsing, cached get_settings() | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `a63acc9a6c63ff4c8918af39cf0fa8610192150d95ad328154a4f7cc3c561874` |
| `backend/database.py` | Async engine and session factory, get_db(), check_database_connection(), dispose_engine() | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `55730ae36a8dfe6b3cc6566475ed76747cdd2ee3c1e5be479c4543d85f967836` |
| `backend/models/__init__.py` | Exports Base and TimestampMixin | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `cbb9baca6a96c4c28c9451fedb1b149aed173cd0cb457203bdd5eace64002821` |
| `backend/models/base.py` | Declarative base, TimestampMixin, utc_now() | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `7e8bd3f5e34d907f43748038d95778a870bfd807a937a4ca840985fe90b81d4e` |
| `backend/schemas/__init__.py` | Exports common schemas | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `7bb9b2b4bfaac6ba448ebd4b4d84021a0af5de1282e9e9b30879131d0a2a5d79` |
| `backend/schemas/common.py` | HealthResponse, ErrorDetail, ErrorResponse | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `7e89ddf34029d4d545bff0f8af03097f8164272cb28e1d5f07b20266fe994d56` |
| `backend/middleware/__init__.py` | Exports AppError and register_error_handlers | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `eb14d3886584cf897d8aa3d315dc1626ae61b683f685959650d5aafc51c69ccf` |
| `backend/middleware/errors.py` | AppError, error handlers, register_error_handlers() | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `e27d6f72e265bc4eb3f67b7347d3ec7d56f897064fb664a6b27562aaa028cf88` |
| `tests/backend/test_config.py` | Configuration tests (17) | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `e4bea71be574d8624a0182e0dc62ce986e47df9994402996ae35aba5be10fe7e` |
| `tests/backend/test_database.py` | Mocked database, session, base and timestamp tests (14) | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `7b43ef5008830c4fdb11ce58d6fbda636092f2f1063f29781e135760f0a6ddd6` |
| `tests/backend/test_errors.py` | Error handling and common schema tests (17) | Implemented; tested in Linux/Python 3.12 scratch env only. Windows/3.14 and repo integration pending | `73fb988b9d660d35b0eb6c0b3fa4e342f3b1ad6deee5ed07770fcfdb8bb55250` |
| `CHECKPOINT.md` | Handoff summary, assumptions, dependencies, decisions, open questions, next steps | Handoff document | n/a |
| `VERIFICATION.md` | What was and was not verified, and in which environment | Handoff document | n/a |
| `MANIFEST.md` | This file | Handoff document | n/a |

Hashes cover the 11 source/test files only; they were taken after a byte-for-byte copy from the verified files.
