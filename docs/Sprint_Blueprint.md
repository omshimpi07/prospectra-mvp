# Prospectra
## Complete MVP Sprint Blueprint v1

### Implementation rule

Build Prospectra as a sequence of small, verifiable vertical slices.

Do not build the entire database, API surface, worker system, or frontend upfront.

At every stage:

```text
Define contract
→ implement minimum required piece
→ test
→ verify
→ integrate
→ continue
```

---

# Sprint 0 — Engineering Foundation

### Goal
Create a clean project that can be developed and tested reliably.

### Build

```text
Repository structure
Environment configuration
Next.js foundation
FastAPI foundation
Supabase connection
PostgreSQL/PostGIS connection
Testing setup
Linting/formatting
Type checking
Basic CI
Health endpoints
Basic logging/error handling
```

### Do not build

```text
Business logic
Full schema
Provider integrations
Search workflow
AI workflow
```

### Verification gate

```text
Frontend starts
Backend starts
Database connects
Tests run
Lint/type checks run
CI passes
```

---

# Sprint 1 — Identity, Workspace & Minimal Domain

### Goal
A real user can enter Prospectra and work inside an isolated workspace.

### Build

Minimum tables/models:

```text
Workspace
WorkspaceMember
ICP
Search
Business
Prospect
Job
```

Authentication:

```text
signup
login
logout
session
```

Workspace:

```text
create workspace
membership
authorization
tenant isolation
```

### Keep minimal

Do NOT implement every conceptual entity yet.

Add:

```text
Evidence
Contact
Signal
Qualification
Activity
Suppression
ResearchRun
UsageEvent
```

only when their functionality arrives.

### Verification gate

```text
User can register/login
Workspace can be created
Workspace isolation works
Database migrations work
Basic domain tests pass
```

---

# Sprint 2 — ICP / Target Definition

### Goal
A seller can describe what they sell and who they want to target.

### Build

ICP builder:

```text
seller description
target business description
geography
basic filters
```

ICP compilation:

```text
natural language
→ AI/provider abstraction
→ structured criteria
→ schema validation
→ supported-criteria validation
```

User must see the interpreted criteria before running a search.

### Important

The AI does not directly control the search.

```text
AI output
→ validation
→ user approval
→ approved ICP
```

### Verification gate

```text
Create ICP
Compile ICP
Validate ICP
Edit ICP
Save ICP
Use approved ICP in search creation
```

---

# Sprint 3 — Search + Job Foundation

### Goal
Create a durable asynchronous search workflow.

### Build

Search API:

```text
create
list
get
cancel
```

Search states:

```text
CREATED
QUEUED
DISCOVERING
NORMALIZING
ENRICHING
QUALIFYING
SCORING
COMPLETED
PARTIAL
FAILED
CANCELLED
```

Job system:

```text
create job
claim job
lease/lock
run job
success
retry
failure
```

Worker runs from the same backend codebase.

### Keep minimal

Only implement the job capabilities required by the first discovery workflow.

### Verification gate

```text
Search creates job
Worker claims job
Worker executes
Search status changes
Failed job retries
Stale job can recover
Browser can close without killing job
```

---

# Sprint 4 — Business Discovery Vertical Slice

### Goal
Run a real search and produce real businesses.

### Build

```text
DiscoveryProvider interface
Overture adapter
Provider DTO
Business normalization
Business persistence
Business source provenance
```

Initial flow:

```text
Approved ICP
→ Search
→ Discovery job
→ Overture
→ normalize
→ Business
```

### Important

The core application must not depend directly on the Overture schema.

### Verification gate

```text
Real search executes
Real businesses returned
Canonical business records created
Source provenance retained
Provider failure handled
```

---

# Sprint 5 — Normalization, Deduplication & Filtering

### Goal
Turn raw discovery results into a clean candidate pool.

### Build

Normalization:

```text
name
category
address
location
website
phone where available
operating status
```

Entity resolution using available signals such as:

```text
provider identity/GERS
domain
phone
name
coordinates
address
```

Deterministic filtering:

```text
geography
category
status
basic ICP filters
```

### Important

Prefer an ambiguous duplicate over an incorrect merge.

### Verification gate

```text
Duplicates detected
Safe matches merged
Ambiguous records preserved
Geographic filtering works
Invalid candidates removed
```

---

# Sprint 6 — Website Intelligence + Contact Routes

### Goal
Understand the digital presence of surviving candidates.

### Build

Safe website fetcher:

```text
HTTP/HTTPS
DNS validation
SSRF protection
redirect validation
timeout
response-size limit
```

Deterministic website analyzer:

```text
reachability
HTTPS
title
meta
viewport
canonical
robots
sitemap
contact page
phone
email
social links
booking
forms
e-commerce signals
basic technical signals
```

Contact routes:

```text
business phone
official email
official contact page
official social profile
appropriate public professional contact
```

### Verification gate

```text
Website safely fetched
SSRF tests pass
Website observations produced
Contact routes have provenance
Failed websites do not kill search
```

---

# Sprint 7 — Evidence + AI Interpretation + Qualification

### Goal
Turn raw observations into trustworthy prospect intelligence.

### Build

Evidence model:

```text
claim
source
reference/URL
observed_at
confidence
```

AI provider abstraction.

AI interpretation for:

```text
website/context understanding
semantic business classification where needed
opportunity interpretation
```

Qualification:

```text
MATCH
NO_MATCH
UNKNOWN
PARTIAL
```

Criterion-by-criterion evaluation.

### AI rules

```text
Structured output
Schema validation
Evidence grounding
No unsupported claims
No direct unrestricted database writes
```

### Verification gate

```text
Every important AI claim is traceable
Unknown remains distinct from No
AI failures degrade gracefully
Qualification can be reproduced
Evidence is visible
```

---

# Sprint 8 — Explainable Scoring + Prospect Workspace

### Goal
Give the salesperson a ranked list they can actually work from.

### Build

Scoring dimensions:

```text
ICP fit
Problem/opportunity evidence
Business attractiveness
Reachability
Data confidence
Freshness
```

Scoring output:

```text
score
priority
reasons
version
```

Prospect workspace:

```text
list
filters
sorting
details
approve
reject
save
notes
tags
status
evidence
contacts
```

Prospect lifecycle:

```text
NEW
REVIEWED
APPROVED
CONTACTED
FOLLOW_UP
INTERESTED
MEETING
WON / LOST
```

### Add now

```text
Activity
Suppression
```

because they are required for the human sales workflow.

### Verification gate

```text
Prospects ranked
Reasoning visible
User can review
Approve/reject works
Suppression works
Notes/status persist
Evidence visible
```

---

# Sprint 9 — Search Orchestration + Resilience + Export

### Goal
Make the complete pipeline reliable enough for actual pilot use.

### Build

Connect:

```text
Discovery
→ normalization
→ deduplication
→ filtering
→ website
→ contacts
→ evidence
→ qualification
→ scoring
→ prospect
```

Improve:

```text
parallel enrichment
retry policy
partial completion
cancellation
idempotency
job recovery
search progress
usage limits
```

Export:

```text
CSV
```

### Verification gate

Run a complete realistic search.

Expected:

```text
Search survives individual failures
Partial results are preserved
Jobs recover
Results are deterministic where expected
CSV export works
Usage limits work
```

---

# Sprint 10 — Selected Prospect Deep Research

### Goal
Allow a salesperson to ask for deeper research on a selected prospect.

### Build

```text
ResearchRun
research jobs
public search
website inspection
existing evidence retrieval
research synthesis
```

Output:

```text
business summary
ICP fit
opportunity signals
evidence
uncertainties
talking points
```

### Important

Research is:

```text
human-triggered
selected-prospect only
evidence-backed
```

No autonomous outbound communication.

### Verification gate

```text
Selected prospect can be researched
Research survives partial failures
Output is structured
Claims have evidence
No outbound actions possible
```

---

# Sprint 11 — MVP End-to-End Hardening

### Goal
Turn the feature set into one coherent product.

### Build/fix

```text
full workflow integration
frontend/backend contract consistency
authorization review
error states
loading states
empty states
partial states
search progress
UX cleanup
basic observability
security review
database/index review
```

Run the complete journey:

```text
signup
→ workspace
→ ICP
→ search
→ real businesses
→ enrichment
→ qualification
→ score
→ prospect review
→ research
→ export
```

### Verification gate

A fresh user can complete the core workflow without developer intervention other than the required external API credentials/configuration.

---

# Sprint 12 — Real-World Pilot Validation

### Goal
Test whether Prospectra is actually useful.

### Build only what validation reveals is necessary.

Prepare benchmark data:

```text
~300 manually verified businesses
```

AI evaluation set:

```text
~100–200 labeled examples
```

Pilot:

```text
2–3 real sellers
```

Measure:

```text
manual research time
Prospectra-assisted research time
approved prospects
rejected prospects
rejection reasons
contactability
later interest/meeting outcomes
useful prospects/hour
```

### Gate

Do not call the MVP successful because the software works.

It must demonstrate that it improves prospecting work for actual users.

---

# Critical Sprint Dependency

The primary path is:

```text
S0 Foundation
 ↓
S1 Identity + Minimal Domain
 ↓
S2 ICP
 ↓
S3 Search + Jobs
 ↓
S4 Discovery
 ↓
S5 Normalize + Dedup
 ↓
S6 Website + Contacts
 ↓
S7 Evidence + Qualification
 ↓
S8 Scoring + Prospect Workspace
 ↓
S9 Full Pipeline Reliability
 ↓
S10 Research
 ↓
S11 E2E Hardening
 ↓
S12 Pilot
```

---

# Parallel Work

After Sprint 3 contracts are stable, limited parallel implementation is possible.

```text
                   Shared Contracts
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     Discovery       Frontend       Website
     Track           Track          Track
          │              │              │
          ▼              ▼              ▼
     Overture        Search UI      Analyzer
     Normalizer      Prospect UI    Extraction
     Dedup           Detail UI      Contact
```

AI adapter work can also proceed independently once its schemas are frozen.

Integration still happens through the shared contracts.

---

# Minimal Initial Schema Strategy

Do not implement the entire conceptual data model at Sprint 1.

### Start with

```text
Workspace
WorkspaceMember
ICP
Search
Business
Prospect
Job
```

### Introduce when needed

```text
BusinessSourceRecord → Sprint 4
ProspectSignal       → Sprint 6/7
Contact              → Sprint 6
Evidence             → Sprint 7
Qualification        → Sprint 7
Activity             → Sprint 8
Suppression          → Sprint 8
UsageEvent           → Sprint 9
ResearchRun          → Sprint 10
SearchResult         → when ranking/search snapshots are implemented
```

This keeps the initial database and routes small.

---

# Minimal Initial API Strategy

Do not create every planned route upfront.

### Early

```text
/auth
/workspaces
/icps
/searches
```

### Then

```text
/prospects
/evidence
/exports
/research
/usage
```

Only add endpoints when their corresponding feature exists.

---

# Claude Implementation Strategy

Every sprint will later be decomposed into small units.

Example:

```text
S4
 ├── S4.1 Business domain
 ├── S4.2 Discovery interface
 ├── S4.3 Overture response DTO
 ├── S4.4 Overture adapter
 ├── S4.5 Normalizer
 └── S4.6 Tests
```

Each unit must specify:

```text
Objective
Context
Scope
Expected files/modules
Interfaces
Inputs
Outputs
Dependencies
Tests
Acceptance criteria
What NOT to change
Verification
```

Claude should receive the minimum context necessary for that unit.

---

# Antigravity Role

Antigravity receives this sprint blueprint and the existing master architecture context.

Before implementation, Antigravity must critically review:

```text
dependency order
scope
missing dependencies
unnecessary infrastructure
schema size
API size
parallelization opportunities
security risks
integration risks
repository constraints
```

Antigravity may recommend corrections.

However:

```text
Product scope
+
core architecture
+
MVP boundary
```

remain controlled decisions.

No silent redesign.

---

# Sprint Handoff Process

For each sprint:

```text
THIS CHAT
 ↓
Sprint specification
 ↓
ANTIGRAVITY
 ↓
critical review
 ↓
corrections
 ↓
final sprint implementation brief
 ↓
CLAUDE
 ↓
small implementation units
 ↓
tests
 ↓
ANTIGRAVITY
 ↓
integration
 ↓
verification
 ↓
next sprint
```

---

# Final Implementation Philosophy

Do not optimize for:

```text
maximum architecture
maximum number of features
maximum AI usage
maximum automation
```

Optimize for:

```text
real working pipeline
small reliable components
low cost
clear evidence
easy debugging
human usefulness
measurable results
```

The first meaningful achievement is not a beautiful dashboard.

It is:

```text
Seller
→ defines target
→ Prospectra discovers real businesses
→ Prospectra researches them
→ Prospectra explains why they may fit
→ salesperson receives a useful prioritized list
```

That is the MVP.