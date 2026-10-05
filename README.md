# Prospectra — Deterministic B2B Prospect Intelligence Platform

> **Prospectra** is an end-to-end B2B local business discovery, web qualification, opportunity scoring, and prioritization platform for agencies, consultants, and B2B service sellers. It replaces manual prospect vetting with verifiable signal extraction, explainable multi-factor scoring, and a human review workspace with CSV export.

---

## 1. Product Overview & Boundaries

Prospectra discovers local businesses, inspects their public web presence, deterministically evaluates their technical qualification against an Ideal Customer Profile (ICP), computes transparent opportunity scores, and provides sellers with an auditable queue for human approval and manual outreach.

### What Prospectra IS
- **Deterministic Discovery Engine:** Queries open spatial data (Overture Maps via DuckDB) by geographic bounding box and category taxonomy.
- **Secure Web Researcher:** Extracts live technical signals (HTTP reachability, SSL security, mobile viewport, CMS platform, public contact info) with defensive anti-SSRF and connection-pinning protections.
- **Deterministic Qualification Engine:** Evaluates requirements using rigid tri-state logic (`QUALIFIED`, `REVIEW_NEEDED`, `DISQUALIFIED`, `UNQUALIFIED`) where missing data is strictly classified as `UNKNOWN` rather than guessed.
- **ICP-Specific Dynamic Opportunity Scorer:** Mathematically weights ICP priorities with status multipliers, yielding bounded `[0.0, 1.0]` ranking scores with transparent factor breakdowns.
- **Human Review & Manual Outreach Workspace:** Next.js interface with an Explainability Drawer, state machine transitions (`PENDING`, `APPROVED`, `REJECTED`), seller notes, and formula-injection-safe CSV export.

### Explicit Product Boundaries (What Prospectra IS NOT)
- **NOT an Autonomous Outreach Bot:** Does **not** send emails, place automated phone calls, or message WhatsApp. A human seller retains complete agency over outreach.
- **NOT a Full CRM:** Does not manage pipelines, deal stages, contracts, invoices, or customer relationships.
- **NOT a Black-Box ML Scorer:** All scores and qualification decisions are mathematical and auditable. AI is strictly optional for unstructured prompt parsing and narrative rationale generation, never a security or decision boundary.

---

## 2. Product Workflow

```
1. Seller Intent       --> Plain text service offering + target categories + target city
2. ICP Compilation     --> AI parses intent into structured criteria (with fallback)
3. ICP Approval        --> Seller reviews and approves ICP version
4. Search Execution    --> Spatial bounding box query against Overture Maps Parquet via DuckDB
5. Web Intelligence    --> In-process worker claims candidates & performs pinned web research
6. Signal Extraction   --> Extracts reachability, SSL, viewport, CMS, and contact channels
7. Deterministic Qual  --> Tri-state rule engine classifies prospect fit
8. Dynamic Scoring     --> Weights prospect signals against seller's ICP criteria
9. Ranked Workspace    --> Seller explores prospects sorted by priority score
10. Human Review       --> Seller inspects evidence, records decision, notes, & exports CSV
```

---

## 3. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Next.js 15 Frontend                           │
│  - App Router, React 19, TypeScript                                    │
│  - TanStack React Query (server state & cache invalidation)            │
│  - Tailwind CSS + Lucide Icons                                         │
│  - /login, /, /workspaces/[workspaceId]/prospects                      │
│  - ProspectDetailDrawer (Explainability, Auditable Evidence, Notes)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS + Bearer JWT
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Modular Monolith                        │
│  - Request ID Correlation Middleware & Unified AppError Exception Tree │
│  - Asymmetric Supabase JWT Verification (JWKS RS256/ES256)             │
│  - Workspace Multi-Tenancy Guarding (404 on Unauthorized Access)       │
│  - Pydantic v2 Validation Schemas                                      │
│  - SQLAlchemy 2.0 (Async) + PostgreSQL (psycopg 3)                     │
└──────┬──────────────────────┬──────────────────────┬───────────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌────────────────────────────┐
│   Supabase   │      │  OpenRouter  │      │       DuckDB Engine        │
│  PostgreSQL  │      │  AI Gateway  │      │  Overture Maps S3 Parquet  │
│  (RLS Enforced)     │ (Free-first) │      │  (Spatial Bounding Boxes)  │
└──────────────┘      └──────────────┘      └────────────────────────────┘
       ▲                                     ▲
       │                                     │
┌──────┴─────────────────────────────────────┴───────────────────────────┐
│                     In-Process Background Workers                      │
│  - SearchWorker: Atomic claim, DuckDB discovery, fault isolation       │
│  - ResearchWorker: Atomic claim, SSRF-pinned web research, evidence   │
│  - Stale Job Recovery: Self-healing timeout monitors on app lifespan  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Architectural Highlights

### Multi-Tenant Isolation & Row Level Security (RLS)
- Every domain entity (`workspaces`, `workspace_members`, `icps`, `searches`, `search_results`, `prospects`, `qualification_evidence`) is partitioned by `workspace_id`.
- Database-level RLS policies enforce tenant boundaries via a `SECURITY DEFINER` non-recursive helper function `public.is_workspace_member()`.
- API endpoints verify workspace membership before processing requests; if a user does not belong to the target workspace, the backend returns a `404 Not Found` (rather than 403) to prevent tenant enumeration attacks.

### SSRF Protection & Connection-Pinning Defense
- All outbound web requests to prospect websites go through `SecureWebFetcher`.
- **IP Validation:** Blocks loopback (`127.0.0.0/8`, `::1`), private RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local addresses, and cloud instance metadata services (`169.254.169.254`).
- **Connection Pinning:** Implements a custom `PinnedAsyncNetworkBackend` (`httpcore`) and `PinnedAsyncHTTPTransport` (`httpx`). This prevents Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks by forcing the underlying TCP socket to connect strictly to the pre-validated IP address, while keeping the original hostname for TLS SNI and HTTP `Host` headers.
- **Defensive Safeguards:** Hard timeouts (5s connect, 10s total), strict response size caps (1 MB), and maximum 3 redirects with re-validation on every redirect hop.

### Deterministic Qualification & Tri-State Logic
- The qualification engine operates strictly on rules, never stochastic LLM output:
  - `TRUE`: Signal explicitly passes requirement.
  - `FALSE`: Signal explicitly fails requirement.
  - `UNKNOWN`: Signal is missing or unverified (e.g. website unresolvable or timeout).
- `UNKNOWN` technical observations never silently count as passing or failing. If a required signal is `UNKNOWN`, the qualification status resolves to `REVIEW_NEEDED` with explicit seller instructions.

### Dynamic ICP-Specific Opportunity Scoring
- Opportunity scores range bounded from `0.0` to `1.0`.
- Mathematical formula:
  $$\text{Priority Score} = \left(\sum \text{Factor Impacts}\right) \times \text{Status Multiplier}$$
- Status multipliers:
  - `QUALIFIED` = `1.00`
  - `REVIEW_NEEDED` = `0.60`
  - `UNQUALIFIED` / `DISQUALIFIED` = `0.00`
- Factor contributions are calculated based on seller ICP weights (e.g. missing website impact, SSL security, category match, mobile viewport).
- Score breakdown is persisted in JSON for explainability and recomputed idempotently during multi-ICP rescores.

### Human Review & Formula-Injection-Safe CSV Export
- Sellers can transition review statuses: `PENDING` $\leftrightarrow$ `APPROVED` $\leftrightarrow$ `REJECTED`.
- Rejection captures structured reasons (`OUT_OF_TERRITORY`, `POOR_OPPORTUNITY`, `CONTACT_UNRESPONSIVE`, `OTHER`).
- Seller notes support debounced autosaving with blur synchronization.
- **CSV Export:** RFC 4180 compliant with CRLF (`\r\n`) terminators. Cell contents starting with formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) are automatically escaped with a leading single quote (`'`) to neutralize CSV formula injection attacks in Microsoft Excel and Google Sheets. Default filter exports `APPROVED` prospects.

### Background Workers Without Heavy Queue Infrastructure
- Uses PostgreSQL as the durable, transactional queue engine via atomic `UPDATE ... WHERE status = 'QUEUED' RETURNING ...` claims.
- **Fault Isolation:** Individual search or research job failures are isolated within independent exception blocks, ensuring a single bad job does not abort batch processing or crash the background polling loop.
- **Stale Job Recovery:** Self-healing recovery automatically transitions stranded jobs (`RUNNING` > 300s for searches, `RESEARCHING` > 120s for research) to `FAILED` with machine-readable error codes.

---

## 5. Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, HTTPX, HTTPCore, DuckDB |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, TanStack React Query v5, Tailwind CSS, Lucide Icons |
| **Database & Auth** | Supabase (PostgreSQL 15+), Supabase Auth (JWT with JWKS asymmetric RS256/ES256 verification), Row Level Security (RLS) |
| **Data Sources** | Overture Maps Foundation (Places theme parquet via AWS S3 / DuckDB spatial querying) |
| **AI Gateway** | OpenRouter (Free-first model routing: `openrouter/free` with mock fallback) |
| **Tooling & Quality** | Pytest, Vitest, Ruff (linter & formatter), Mypy (strict type checking) |

---

## 6. Environment Configuration

### Backend Configuration (`.env`)
Create a `.env` file in the root directory:
```bash
# Application
ENVIRONMENT=development
DEBUG=false

# Database (Supabase PostgreSQL via connection pooling or direct)
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@<pooler-host>:5432/postgres

# CORS (Frontend URL)
CORS_ORIGINS=http://localhost:3000

# Supabase Auth
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<your-supabase-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-supabase-service-role-key>

# AI Provider Gateway (OpenRouter)
AI_PROVIDER=openrouter
AI_MODEL=openrouter/free
OPENROUTER_API_KEY=<your-openrouter-api-key>

# Discovery Provider
DISCOVERY_PROVIDER=overture

# Web Intelligence Worker Defaults
WEB_FETCH_TIMEOUT_SECONDS=10.0
WEB_CONNECT_TIMEOUT_SECONDS=5.0
WEB_MAX_RESPONSE_BYTES=1048576
WEB_MAX_REDIRECTS=3
RESEARCH_WORKER_POLL_INTERVAL_SECONDS=2.0
RESEARCH_JOB_TIMEOUT_SECONDS=120.0
SEARCH_WORKER_POLL_INTERVAL_SECONDS=2.0
SEARCH_JOB_TIMEOUT_SECONDS=300.0
```

### Frontend Configuration (`frontend/.env.local`)
Create a `frontend/.env.local` file:
```bash
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## 7. Local Development Setup

### Prerequisites
- Python 3.12 or newer
- Node.js 18+ and npm
- Active Supabase project (or local Supabase CLI instance)

### 1. Backend Setup
```bash
# 1. Create and activate virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.lock

# 3. Start the FastAPI development server
uvicorn backend.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start the Next.js development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to access the application.

---

## 8. Verification & Testing

### Backend Test Suite & Code Quality
```bash
# Run 200+ unit, integration, and security tests
pytest

# Code linting
ruff check .

# Code formatting check
ruff format --check .

# Static type checking
mypy backend
```

### Frontend Test Suite & Production Build
```bash
cd frontend

# Run component and page unit tests
npm test -- --run

# Compile optimized production build and verify TypeScript types
npm run build
```

### Database Migrations
Migrations are managed via the Supabase CLI:
```bash
# Check migration history status
npx supabase migration list --db-url "$DATABASE_URL"
```

---

## 9. Current Limitations & Future Roadmap

- **Geographic Support:** Discovery is currently optimized for Indian metropolitan hubs (Pune, Mumbai, Delhi, Bengaluru, Hyderabad, Chennai) with bounding-box spatial projections.
- **External Network Dependency:** Live discovery queries Overture Maps parquet files hosted on AWS S3 via DuckDB; offline execution falls back cleanly to the built-in `MockDiscoveryProvider`.
- **Single-Process Monolith:** Workers run asynchronously within the FastAPI lifespan loop. Suitable for single-instance or small multi-worker deployments without requiring external broker infrastructure (Redis/Celery).

---

## 10. License

Prospectra is proprietary software developed for high-trust B2B prospect intelligence. All rights reserved.
