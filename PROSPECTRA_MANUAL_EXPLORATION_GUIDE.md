# Prospectra — Manual Exploration & Evaluation Guide

**Repository**: `https://github.com/omshimpi07/prospectra-mvp.git`  
**Current Release**: Sprint 8 (`2528bed`)  
**Target Audience**: Product Owner / Evaluator (Manual Testing & Exploration)  

---

## Welcome to the Prospectra Exploration Guide

This document is your step-by-step handbook to explore and evaluate the live Prospectra application as of Sprint 8. It contains exact commands, routes, actions, inputs, and expected responses so you can personally test every aspect of the platform from a human seller's perspective.

---

## PART 2 — Exact Local Startup Instructions

### 1. Prerequisites Before Starting
- **Python**: Version 3.12 or newer (Windows/macOS/Linux).
- **Node.js**: Version 18.x or newer, with `npm`.
- **Database & Auth (Supabase)**: You must have an active Supabase project (either hosted at `supabase.com` or running locally via `npx supabase start`).
- **Network**: Internet access is needed if using live Overture S3 discovery or live OpenRouter AI. (If offline, mock providers can be used).

### 2. Environment Variables Configuration

You need two environment files: one at the root for the backend, and one inside `frontend/` for Next.js.

#### A. Backend Environment File (`.env` in root `D:\Prospectra\.env`)
Create or edit `.env` in the repository root:
```ini
# Application Mode
ENVIRONMENT=development
DEBUG=true

# Database (Must start with postgresql+psycopg://)
# Use your Supabase PostgreSQL connection string:
DATABASE_URL=postgresql+psycopg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# CORS (Frontend origin)
CORS_ORIGINS=http://localhost:3000

# Supabase Auth Configuration
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=[your-supabase-anon-key]
SUPABASE_SERVICE_ROLE_KEY=[your-supabase-service-role-key]

# AI Provider Gateway (Sprint 2 Free-First Architecture)
# Safe options: 'openrouter' (if you have a free key) OR 'mock' (requires no key!)
AI_PROVIDER=openrouter
AI_MODEL=openrouter/free
OPENROUTER_API_KEY=[your-openrouter-key]

# Discovery Provider (Sprint 3 Overture + DuckDB Architecture)
# Safe options: 'overture' (queries live AWS S3 Parquet via DuckDB) OR 'mock' (instant offline synthetic businesses)
DISCOVERY_PROVIDER=overture

# In-Process Worker Defaults
SEARCH_WORKER_POLL_INTERVAL_SECONDS=2.0
RESEARCH_WORKER_POLL_INTERVAL_SECONDS=2.0
SEARCH_JOB_TIMEOUT_SECONDS=300.0
RESEARCH_JOB_TIMEOUT_SECONDS=120.0
```

#### B. Frontend Environment File (`frontend/.env.local` in `D:\Prospectra\frontend\.env.local`)
Create or edit `frontend/.env.local`:
```ini
NEXT_PUBLIC_SUPABASE_URL=https://[project-ref].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=[your-supabase-anon-key]
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 3. Which Values Are Safe to Configure Manually?
- **`DISCOVERY_PROVIDER=mock`**: **100% safe.** Allows testing prospect search and discovery without connecting to AWS S3. Returns deterministic Indian businesses in Pune (e.g., Blue Tokai, German Bakery, Vaishali).
- **`AI_PROVIDER=mock`**: **100% safe.** Allows testing ICP compilation without needing an OpenRouter account or API key.
- **`DEBUG=true`**: Safe for local development to see detailed FastAPI log output.
- **`CORS_ORIGINS`**: Set to `http://localhost:3000` to allow the Next.js frontend to communicate with the FastAPI backend.

### 4. Supabase & OpenRouter Requirements
- **Must Supabase be running/connected?** **YES.** Supabase PostgreSQL stores workspaces, ICPs, searches, prospects, notes, and evidence. Supabase Auth generates the JWT tokens required to authenticate frontend API calls.
- **Must OpenRouter be configured?** **NO.** If you set `AI_PROVIDER=mock`, the backend uses the built-in deterministic `MockAIProvider` and requires no API key. If you set `AI_PROVIDER=openrouter`, you will need an OpenRouter key from `openrouter.ai/keys`.
- **Is Overture live discovery available locally?** **YES.** DuckDB executes spatial bounding box queries directly against public Overture Parquet on AWS S3 over HTTPS without needing local geospatial software installed. If you prefer offline/instant discovery, switch `DISCOVERY_PROVIDER=mock`.

### 5. Backend Startup Command
In your backend terminal (from `D:\Prospectra`):
```powershell
# 1. Activate your virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Ensure uvicorn is installed in your virtual environment
pip install uvicorn

# 3. Start the FastAPI application server
uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```
You should see:
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```
*(The background SearchWorker and ResearchWorker automatically boot as part of the lifespan loop).*

### 6. Frontend Startup Command
In a **second terminal** (from `D:\Prospectra\frontend`):
```powershell
# 1. Start the Next.js development server
npm run dev
```
You should see:
```text
   ▲ Next.js 15.1.0
   - Local:        http://localhost:3000
   - Environments: .env.local

 ✓ Starting...
 ✓ Ready in 1.8s
```

---

## PART 3 — URLs & Routes to Open

| Route | Full URL | Purpose |
|:---|:---|:---|
| **`/login`** | `http://localhost:3000/login` | Authentication gateway: Sign up for a new seller account or sign in to an existing account. |
| **`/`** | `http://localhost:3000/` | Root entry point: Resolves active workspaces. Automatically redirects to your prospects queue or shows the inline workspace creation form. |
| **`/workspaces/[workspaceId]/prospects`** | `http://localhost:3000/workspaces/{id}/prospects` | **Main Workspace**: Deterministic opportunity queue, filter bars, priority ranking table, and export button. |
| **Drawer Query** | `http://localhost:3000/workspaces/{id}/prospects?prospectId={id}` | Opens the Prospect Detail & Explainability Drawer for deep inspection of any prospect. |

### Where Should You Start?
👉 **Start at `http://localhost:3000/`**.  
If you are not logged in, you will be automatically redirected to `http://localhost:3000/login`.

---

## PART 4 — First-Time Seller Walkthrough

Follow this step-by-step script using a realistic prospecting scenario:

- **Your Role**: Founder of a web design agency.
- **Your Service**: Website redesign + mobile optimization + online ordering.
- **Target Market**: Restaurants, cafes, and bakeries.
- **Location**: Pune, Maharashtra.

---

### Step 1: Account Creation & Sign In
1. Open your browser to `http://localhost:3000/`.
2. The browser automatically navigates to `http://localhost:3000/login`.
3. Click the bottom link: **"Need an account? Sign Up"**.
4. Enter your email (e.g., `seller@example.com`) and a password (e.g., `password123`).
5. Click **"Sign Up"**.
   - *Expected Result*: A green alert confirms account creation.
6. Now enter those credentials and click **"Sign In"**.
   - *Expected Result*: The page navigates to `/`.

---

### Step 2: Create Your First Workspace
1. If this is a brand new account with 0 workspaces, you will see the **"Welcome to Prospectra"** screen.
2. In the **Workspace Name** field, enter:
   `Apex Web Studio`
3. Click **"Create Workspace & Start"**.
   - *Expected Result*: A brief spinner appears, the workspace is provisioned in the database, and you are automatically redirected to `http://localhost:3000/workspaces/[your-workspace-uuid]/prospects`.

---

### Step 3: Understand the Empty Queue State
1. You land on the **Prospect Intelligence Workspace**.
2. Because no searches have been executed yet, you will see a clean onboarding card:
   - Icon: Blue search magnifying glass.
   - Title: **"No prospects in this workspace yet"**.
   - Subtitle: *"Start by discovering local businesses matching your target offering, then let Prospectra qualify and rank them."*
   - Primary Button: **"Find Prospects Now"**.
3. In the top navigation bar, notice the blue **"Find Prospects"** button next to the refresh and export buttons.

---

### Step 4: Launch Guided Discovery
1. Click **"Find Prospects Now"** (or the **"Find Prospects"** button in the header).
2. The **Find New Prospects** modal appears over the workspace.
3. Review or fill in the guided fields:
   - **Service Offering**: `Modern Website Redesign & Online Ordering`
   - **Target Business Category**: `Restaurants & Cafes`
   - **Target City**: `Pune`
   - **Website Filter**: Keep on `Any (Include businesses without websites)`
   - **Maximum Candidates**: `20`
4. Click **"Start Discovery & Scoring"**.

---

### Step 5: Observe Live Multi-Stage Progress
Watch the 3-step live stepper inside the modal:
1. **Stage 1 (Structuring Seller Pitch)**:
   - The system calls the ICP compilation API.
   - Status text: *"Analyzing pitch and structuring Ideal Customer Profile..."*
   - A green checkmark appears once the ICP is compiled and approved.
2. **Stage 2 (Scanning Local Businesses)**:
   - The system calls DuckDB spatial search over Overture Places data in Pune.
   - Status text: *"Querying business map data in Pune..."*
   - A green checkmark appears when candidate businesses are found.
3. **Stage 3 (Qualifying Candidates & Scoring)**:
   - The system promotes discovered businesses into the qualification and scoring pipeline.
   - Status text: *"Evaluating web signals and computing priority scores..."*
   - Status updates: *"Found X business prospects! Initial scores computed."*
4. The modal closes automatically after 1.8 seconds, and your table refreshes.

---

### Step 6: Explore the Ranked Prospect Queue
1. You are back on `/workspaces/[workspaceId]/prospects`.
2. The table is now populated with ranked businesses, sorted from highest priority score to lowest.
3. Examine the columns:
   - **Priority**: A colored percentage badge (e.g. `92%` or `80%`).
   - **Business & Category**: Business name (e.g. "Blue Tokai Coffee Roasters", "German Bakery"), category tag (`cafe`, `bakery`), and city (`Pune`).
   - **Core Opportunity**: A concise summary of why this business is ranked (e.g., *"High opportunity: active cafe missing mobile viewport"* or *"Acute opportunity: business has no website"*).
   - **Channels**: Visual contact icons (Globe for website, Phone for telephone, Mail for public email).
   - **Review Status**: Badge showing `UNREVIEWED` in gray.
   - **Quick Action**: Green checkmark (Approve) and Rose X (Reject).

---

### Step 7: Filter the Queue
1. In the search box, type `Bakery`.
   - *Expected Result*: The table instantly filters locally to show only bakeries. Clear the box.
2. Click the **"Priority $\ge 80\%$ (High)"** dropdown filter.
   - *Expected Result*: Only high-opportunity prospects are shown; URL updates with `?min_score=0.80`.
3. Click the **"Needs Review (REVIEW_NEEDED)"** dropdown filter.
   - *Expected Result*: URL updates with `?qual=REVIEW_NEEDED`.
4. Click **"Reset filters"** on the right side of the filter bar to return to the full queue.

---

### Step 8: Inspect a Prospect (Open Explainability Drawer)
1. Click on the row of the top-ranked prospect.
2. The slide-over **Prospect Detail Drawer** opens on the right side of your screen.
3. Notice that the URL updates to `?prospectId=[uuid]`.
4. Inspect the three sections of the drawer:
   - **Outreach Action Bar**: Check for active buttons for Email, Call, WhatsApp, and Website. Click **"Copy Info"** and observe the "Copied" toast.
   - **Human Seller Decision**: See your review controls and private notes.
   - **Algorithmic Qualification & Opportunity**: Review the system's deterministic verdict, qualification rationale, and the **Factor Decomposition** table showing exact mathematical point contributions.
   - **Audit Trail (Technical Evidence)**: Expand the technical probe logs to view HTTP status, SSL status, and mobile viewport detection.

---

### Step 9: Record a Human Review Decision & Seller Note
1. In the **Human Seller Decision** section, click **"Approve for Outreach"**.
   - *Expected Result*: The button turns solid emerald green with a checkmark. In the background table, the prospect's review badge updates to `APPROVED`.
2. Scroll to the **Seller Note (Private)** textarea.
3. Type:
   `Called manager Rahul. Owner Anita visits on Tuesday mornings.`
4. Watch the top right of the note field:
   - It transitions from *"Saving..."* with a spinner to a green *"Saved"* checkmark within 600ms.
5. Close the drawer by clicking the **"X"** button at the top right.

---

### Step 10: Test Rejection with Mandatory Reason
1. Click on a lower-ranked prospect row to open the drawer.
2. Click the red **"Reject"** button.
   - *Expected Result*: The button highlights red, and a **"Rejection Reason (Required)"** dropdown appears immediately beneath it.
3. In the dropdown, select **"Not a fit for our niche/offering"**.
   - *Expected Result*: The rejection reason is persisted immediately to the backend.
4. Close the drawer.
5. In the top filter tabs, click the **"Rejected"** tab.
   - *Expected Result*: The prospect you just rejected appears in this tab.
6. Click back to the **"All Queue"** tab.

---

### Step 11: Export Approved Prospects to CSV
1. In the top navigation bar, click the dark button: **"Export Approved CSV"**.
2. A spinner appears on the button while the backend prepares the RFC 4180 CSV file.
3. The browser downloads a file named:
   `prospects_[workspaceId]_approved_[timestamp].csv`
4. Open the CSV in Microsoft Excel, Google Sheets, or a text editor.
5. Verify the contents:
   - Only the prospect you **Approved** is included in the export (the unreviewed and rejected prospects are excluded).
   - Check that all 14 columns are populated: Business Name, Category, City, Website, Priority Score, Qualification Status, Human Review Status, Core Opportunity, Public Email, Phone, Seller Note, etc.

---

## PART 5 — Explain the Find Prospects Flow

### From a Seller's Perspective
When you click **"Find Prospects"**, you do not need to construct complex Boolean search queries or configure database scrapers. You describe what you sell, who you want to sell to, and where. 

The system guides you through three fields:
1. **What service do you offer?** (e.g., *Modern Website Redesign & Online Ordering*). This tells Prospectra what technical weaknesses to look for in businesses.
2. **Target Business Category** (e.g., *Restaurants & Cafes*). This narrows map scanning to relevant local establishments.
3. **Target City** (e.g., *Pune*). This sets the geographic boundary.
4. **Website Filter**: You can choose whether to include businesses that have no website at all, only businesses with existing websites, or any business.

When you click "Start Discovery", a 3-step live progress indicator shows you exactly what is happening:
- Step 1: Converting your pitch into an Ideal Customer Profile.
- Step 2: Scanning local business map data.
- Step 3: Researching websites, testing technical signals, and computing opportunity scores.

When complete, the modal congratulates you with the count of prospects discovered and places them immediately into your workspace queue, sorted with the best opportunities at the top.

---

### Technical Explanation (Under the Hood)
When the seller clicks "Start Discovery & Scoring", the frontend executes an orchestrated sequence of API calls:
```
1. POST /api/v1/workspaces/{id}/icps
   Payload: { "service_offering": "..." }
   -> Creates draft ICP record in PostgreSQL.

2. POST /api/v1/workspaces/{id}/icps/{icp_id}/compile
   Payload: { "prompt": "Service: ... Target: ... City: ..." }
   -> OpenRouter (or MockAIProvider) parses the prompt into a structured CompiledICPCriteria schema.

3. POST /api/v1/workspaces/{id}/icps/{icp_id}/approve
   -> Transitions ICP status from DRAFT to APPROVED.

4. POST /api/v1/workspaces/{id}/searches
   Payload: { "city": "Pune", "target_categories": [...], "limit": 20 }
   -> Queues a spatial search in the searches table.

5. POST /api/v1/workspaces/{id}/searches/{search_id}/run
   -> Triggers in-process DuckDB spatial query against Overture Maps Parquet on AWS S3.
   -> Populates search_results table with discovered candidates.

6. GET /api/v1/workspaces/{id}/searches/{search_id} (Polling)
   -> Polls until search.status == "COMPLETED".

7. GET /api/v1/workspaces/{id}/searches/{search_id}/results
   -> Retrieves IDs of discovered candidates.

8. POST /api/v1/workspaces/{id}/prospects/qualify-candidates
   Payload: { "search_result_ids": [...] }
   -> Enqueues candidates into the prospects table with initial qualification and priority score.
```

---

## PART 6 — What the System Actually Does (Internal Intelligence Flow)

```
SELLER INPUT
   ↓
ICP COMPILATION (Structured Criteria)
   ↓
SPATIAL DISCOVERY (Overture Maps via DuckDB)
   ↓
WEB RESEARCH (Anti-SSRF Pinned Probe)
   ↓
DETERMINISTIC QUALIFICATION (Tri-State Logic)
   ↓
DYNAMIC SCORING (Mathematical Weighting)
   ↓
DETERMINISTIC RANKING (Score-First Sorting)
   ↓
HUMAN REVIEW (Seller Decision & Notes)
```

| Pipeline Stage | Inputs | Outputs | System / Provider Involved | Deterministic vs. AI | What Evidence Is Collected | What Can Become `UNKNOWN` | What the Seller Sees in the UI |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **1. Seller Input** | Plain text pitch, category, city | Raw prompt string | Frontend Form | User input | None | Nothing | Input modal fields |
| **2. ICP Compilation** | Raw prompt | `CompiledICPCriteria` JSON schema | OpenRouter AI (`openrouter/free`) or `MockAIProvider` | AI (bounded by strict Pydantic schema validation) | None | Category classification if unrecognized | Stage 1 "Structuring Seller Pitch" spinner |
| **3. Spatial Discovery** | Geographic bounding box + categories | Discovered business candidates | DuckDB Engine querying Overture Maps Parquet on AWS S3 | **100% Deterministic** | Business name, lat/long, category, address, phone, website URL | Missing website or missing phone in map records | Stage 2 "Scanning Local Businesses" |
| **4. Web Research** | Candidate website URL | Raw technical signals | `SecureWebFetcher` with anti-SSRF IP pinning & timeouts | **100% Deterministic** | HTTP status code, SSL cert validity, mobile viewport tag, CMS fingerprints | Website unreachable, domain unresolvable, connection timeout | Detailed probe cards in Drawer Audit Trail |
| **5. Qualification** | Extracted signals vs. ICP rules | Status: `QUALIFIED`, `REVIEW_NEEDED`, `UNQUALIFIED` | `QualificationEngine` | **100% Deterministic** (Tri-state boolean rule logic) | Evaluated signal values | Unreachable websites or missing viewport tags resolve to `REVIEW_NEEDED` | Qualification Tier badge: "Qualified Fit", "Needs Review" |
| **6. Opportunity Scoring** | Qualified signals + ICP profile | `priority_score` (0.0 to 1.0) and factor breakdown | `ScoringEngine` | **100% Deterministic** ($\sum \text{impacts} \times \text{multiplier}$) | Individual factor scores (`+0.25`, `+0.40`) | Missing signals award 0.0 points | Score badge (e.g. `92%`), Factor Decomposition table |
| **7. Ranking** | All workspace prospects | Ordered list | PostgreSQL SQL query (`ORDER BY priority_score DESC`) | **100% Deterministic** | Priority score, qualification tier, creation date | Prospects with equal score tie-break by ID | Ordered table on main workspace |
| **8. Human Review** | Seller clicks & notes | Updated review status, reason, seller note | PostgreSQL + TanStack Query cache | **100% Human Seller Decision** | User ID, review timestamp, note text | Human decision is never overridden by AI | Green checkmark, Approved status, private notes |

---

## PART 7 — How to Inspect a Prospect

When you click on any business in the queue, the **Prospect Detail Drawer** slides open. Here is how to evaluate each section:

```
┌─────────────────────────────────────────────────────────────┐
│  [92%]  [cafe] • Pune                                   [X] │
│  Blue Tokai Coffee Roasters                                 │
├─────────────────────────────────────────────────────────────┤
│  DIRECT HUMAN OUTREACH                                      │
│  [Email]   [Call]   [WhatsApp]   [Website]    [Copy Info]   │
├─────────────────────────────────────────────────────────────┤
│  HUMAN SELLER DECISION                                      │
│  [Approve for Outreach]   [Reject]   [Reset]                │
│  Seller Note: "Spoke to manager..."                         │
├─────────────────────────────────────────────────────────────┤
│  ALGORITHMIC QUALIFICATION & OPPORTUNITY                    │
│  Status: QUALIFIED • Qualified Fit                          │
│  Rationale: "High opportunity: active cafe missing mobile"  │
│  Factor Decomposition:                                      │
│    • Lacks Mobile Viewport        +0.25 / 0.25  [matched]   │
│    • Insecure / Missing SSL       +0.15 / 0.15  [matched]   │
│    • Target Category Match        +0.25 / 0.25  [matched]   │
├─────────────────────────────────────────────────────────────┤
│  AUDIT TRAIL (TECHNICAL EVIDENCE)                           │
│  • Website Reachability & HTTP Status: HTTP 200 Reachable   │
│  • Mobile Optimization & Viewport: Meta tag absent          │
│  • SSL / HTTPS Security: Valid certificate                  │
│  [▶ View Raw Probe JSON]                                    │
└─────────────────────────────────────────────────────────────┘
```

### Critical Distinction: System Conclusion vs. Human Review Decision

| Property | System Conclusion (Algorithmic) | Human Review Decision (Seller Agency) |
|:---|:---|:---|
| **What it represents** | The software's mathematical calculation based on public web evidence. | The human seller's real-world sales verdict. |
| **Where it appears** | "Algorithmic Qualification & Opportunity" card and Priority Score badge. | "Human Seller Decision" card and table Review badge. |
| **Can it change automatically?** | Yes, if signals are re-crawled or the ICP is rescored. | **Never.** The system will never overwrite a human approval or rejection. |
| **Allowed Values** | `QUALIFIED`, `REVIEW_NEEDED`, `UNQUALIFIED`, `DISQUALIFIED`. | `UNREVIEWED`, `APPROVED`, `REJECTED`. |
| **Default CSV Export** | All qualification tiers can be exported if approved. | **Only `APPROVED` prospects are exported by default.** |

---

## PART 8 — Evidence & Signals: How to Decide if You Trust a Prospect

In the **Audit Trail (Technical Evidence)** section of the Drawer, Prospectra shows the exact crawler observations.

### What to Look for to Decide Trust:
1. **Website Reachability & HTTP Status**:
   - Look for `HTTP Status 200, Reachable=True`.
   - If the site returned `404 Not Found` or `500 Server Error`, you will see it clearly reported in the probe card.
2. **SSL / HTTPS Security Certificate**:
   - Shows whether the site is running secure HTTPS (`ssl_valid: true`).
   - If the SSL certificate is expired or missing, it is flagged as an acute opportunity for modernization.
3. **Mobile Optimization & Viewport**:
   - Shows whether the HTML contains `<meta name="viewport" content="...">`.
   - If missing, the site does not adapt to smartphones, representing an immediate pitch angle.
4. **Content Management & Tech Stack**:
   - Shows detected CMS signatures (e.g. WordPress, Wix, Squarespace, Shopify).
5. **Raw Technical Transparency**:
   - Click **"View Raw Probe JSON"** under any signal card. This displays the raw crawler JSON payload (IP address, response time, header status) so technical sellers can audit the crawler directly.

### What Does the System Do When Evidence is Insufficient?
- **It NEVER guesses or hallucinates.**
- If a website fails to respond, times out, or blocks the probe, the signal value is marked as `UNKNOWN`.
- The qualification status automatically resolves to `REVIEW_NEEDED` (Needs Human Review).
- The priority score applies a conservative `0.60` status multiplier rather than full credit.
- The seller is presented with an explicit explanation: *"Mobile viewport could not be determined due to unread/unreachable page; human verification required."*

---

## PART 9 — Scoring Exploration & The S8 No-Website Opportunity Behavior

### How the Score is Calculated
The priority score is computed by a deterministic formula:
$$\text{Priority Score} = \left(\sum \text{Matched Factor Impacts}\right) \times \text{Status Multiplier}$$
- Status Multipliers:
  - `QUALIFIED` = `1.00` (Full score)
  - `REVIEW_NEEDED` = `0.60` (40% confidence discount due to unverified signals)
  - `UNQUALIFIED` / `DISQUALIFIED` = `0.00` (Zeroed out)

### Testing the S8 "No-Website Opportunity" Behavior
Before Sprint 8, if a business in the map database had **no website**, it received 0 points for mobile gap, 0 points for SSL gap, and 0 points for domain presence—resulting in a low score (~0.40) despite being the prime target for an agency building websites!

In Sprint 8, Prospectra introduced the `no_website_opportunity` factor:
1. When `website_exists` is `False`:
   - The engine does not penalize the business.
   - It awards a dedicated **`+0.40 / 0.40`** factor: *"No Existing Website: Business has no public website; prime prospect for new website development."*
   - Combined with Category Match (`+0.25`) and Reachable Phone Channel (`+0.15`), the business achieves a high score (**0.80 / 80%** or higher).
2. **How to observe this in the UI**:
   - Look for a business in the table that shows a disabled gray "No Website" globe.
   - Click the row to open the Drawer.
   - Look at the **Factor Decomposition** table.
   - You will see:
     ```text
     No Existing Website       +0.40 / 0.40    [matched]
     Evidence: Business has no public website; prime prospect for new website development.
     ```
   - This proves that businesses without websites are properly prioritized for website development sellers.

---

## PART 10 — Human Review: Approvals, Rejections, and Notes

### 1. Approving a Prospect
- **Action**: Click "Approve for Outreach" in the Drawer (or the green checkmark in the table).
- **Expected UI**: Button highlights green with a checkmark. Table badge changes to `APPROVED`.
- **Persistence**: Saved to Supabase in `prospects.review_status = 'APPROVED'`, `reviewed_at = now()`, `reviewed_by = user_id`.

### 2. Rejecting a Prospect
- **Action**: Click "Reject" in the Drawer.
- **Expected UI**: The button highlights red. A mandatory **"Rejection Reason (Required)"** dropdown appears.
- **Persistence**: Selecting a reason saves `prospects.review_status = 'REJECTED'` and `prospects.rejection_reason = '...'`.

### 3. Reversing a Decision (Resetting)
- **Action**: Click the "Reset" button in the Drawer.
- **Expected UI**: Review status returns to `UNREVIEWED`. Rejection reason dropdown disappears.
- **Persistence**: Saved to Supabase with `review_status = 'UNREVIEWED'` and `rejection_reason = NULL`.

### 4. Qualitative Seller Notes & Debounced Autosave
- **Action**: Click into the "Seller Note (Private)" textarea and type notes.
- **Expected UI**:
  - As you type, the character count updates (`X / 1000`).
  - Top right displays amber text: *"Saving..."* with a spinner.
  - 600ms after you stop typing, it switches to green: *"Saved"* with a checkmark.
- **Persistence**: Note is saved to `prospects.seller_note` in PostgreSQL. If you reload the page, your note remains intact.

---

## PART 11 — CSV Export

### Where Does Export Exist?
In the top right navigation bar on `/workspaces/[workspaceId]/prospects`, labeled **"Export Approved CSV"**.

### Default Behavior & Filtering
- **Default Filter**: Exports all prospects where `review_status = 'APPROVED'`.
- **Tab Sensitivity**: If you are on the "Rejected" tab, it exports rejected prospects; on "All Queue", it exports approved prospects by default.
- **Sorting**: Prospects in the CSV are ordered identically to the workspace queue: highest priority score first.

### The 14 Exported Columns
1. `Business Name`
2. `Canonical Category`
3. `City`
4. `Website`
5. `Priority Score` (formatted to 2 decimal places, e.g. `0.92`)
6. `Scoring Profile` (e.g. `WEB_REDESIGN_MODERNIZATION`)
7. `Qualification Status` (`QUALIFIED`, `REVIEW_NEEDED`, `UNQUALIFIED`)
8. `Human Review Status` (`APPROVED`, `REJECTED`, `UNREVIEWED`)
9. `Core Opportunity` (Plain text rationale summary)
10. `Public Email` (Comma-separated public emails)
11. `Phone` (Reachable telephone number)
12. `Rejection Reason` (Populated if rejected, blank if approved)
13. `Seller Note` (Your private qualitative notes)
14. `Discovered At` (Timestamp formatted as `YYYY-MM-DD HH:MM:SS`)

### Formula Injection Defense
If a business name or note begins with Excel formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`), Prospectra automatically prefixes a single quote (`'`). This prevents malicious spreadsheet command execution when opening the CSV in Microsoft Excel or Google Sheets.

---

## PART 12 — Edge Case & Failure Testing Checklist

Use this checklist to deliberately test the boundaries and error handling of the product:

| # | Test Scenario | Action | Expected System Behavior | What Would Indicate a Bug |
|:---:|:---|:---|:---|:---|
| **1** | **New account with 0 workspaces** | Register a brand new user and log in. | Routes to `/`, displays "Welcome to Prospectra" with the inline workspace creator. | Blank page, infinite spinner, or 404 error. |
| **2** | **Invalid / empty seller input** | Open Find Prospects modal, clear the Service Offering input, click Start. | HTML5 input validation prevents submission ("Please fill out this field"). | Backend 500 error or silent failure. |
| **3** | **Missing target category** | In modal, enter spaces only in Category. | Submit button is blocked by validation. | Blank categories sent to backend. |
| **4** | **Missing city** | In modal, enter empty city. | Blocked by required form input validation. | Geocoding failure or unhandled exception. |
| **5** | **Search with no results** | In modal, search for a non-existent category in a tiny radius. | Search completes gracefully with 0 results; queue shows context-aware empty state. | Infinite spinner or unhandled crash. |
| **6** | **Search still running** | Open modal, submit search, watch progress. | Progress shows "Scanning Local Businesses..." and polls until complete. | Modal hangs permanently without updating. |
| **7** | **Discovery failure** | Disconnect internet while using live Overture. | Modal displays red error alert: *"Discovery failed: ... "* with a "Try Again" button. | Silent freeze or white screen. |
| **8** | **Website unavailable** | Inspect a business whose website is down or offline. | Crawler records HTTP error; signal marked as `UNKNOWN`; qualification marked `REVIEW_NEEDED`. | Crawler crashes or marks prospect `QUALIFIED`. |
| **9** | **Qualification UNKNOWN** | Inspect prospect with `REVIEW_NEEDED`. | Status badge shows amber "Needs Human Review" with explanation of missing signal. | Missing signal counted as passing. |
| **10** | **Prospect with no website** | Inspect business with no website in web design profile. | Receives `no_website_opportunity` factor (`+0.40`); score is high ($\ge 0.70$). | Score drops to 0.0 or displays NaN. |
| **11** | **Prospect with weak evidence** | Inspect business with missing contact info. | Email/WhatsApp buttons show disabled gray state ("No Email", "No WhatsApp"). | Broken link or mail client opened with empty recipient. |
| **12** | **Reject without reason** | Click Reject in Drawer, observe dropdown. | Dropdown defaults to "Poor gap opportunity" or requires selection; cannot submit empty reason. | Backend allows rejection without reason. |
| **13** | **Reverse a human review** | Approve a prospect, then click Reset. | Status returns to `UNREVIEWED`; badge updates; rejection reason is cleared. | Previous review status remains stuck. |
| **14** | **Empty prospect queue** | In a workspace with no prospects, visit `/prospects`. | Displays prominent empty state with "Find Prospects Now" primary CTA. | Broken table headers with no guidance. |
| **15** | **Export with no approved prospects** | In a fresh workspace with 0 approved prospects, click Export. | Downloads a valid CSV containing only the header row, without crashing. | Backend 500 error or corrupted file. |

---

## PART 13 — User Experience Evaluation Questions

As you walk through the screens, ask yourself these 10 core product questions:

1. **Clarity of Purpose**: When I land on this screen, do I immediately understand what it is for?
2. **Actionability**: Do I know what my next single action should be without guessing?
3. **Terminology**: Are the terms seller-friendly (e.g. "Qualified Fit", "Needs Review", "Approved") or do they feel like raw database enums?
4. **Transparency**: When the system is working, does it tell me what it is doing, or does it leave me staring at an uninformative spinner?
5. **Comprehension**: Do I understand why the #1 ranked prospect is ranked higher than the #10 prospect?
6. **Trust & Verifiability**: When I look at the evidence, do I trust that the business actually has this technical gap, or do I feel like the AI made it up?
7. **Error Recovery**: If something goes wrong, does the app give me a clear explanation and a way to try again?
8. **Efficiency**: Does the interface let me review and qualify 10 prospects in under 2 minutes?
9. **Cognitive Load**: Is there any technical jargon (e.g. JSON blobs, UUIDs) that gets in the way of sales outreach?
10. **Simplicity**: Could any screen or step be made simpler without sacrificing evidence and trust?

---

## PART 14 — Known Limitations

The following limitations are **expected behavior** within the MVP scope:

1. **Geographic Coverage**:
   - *Status*: Expected MVP behavior.
   - *Detail*: Live Overture spatial queries are currently calibrated for major Indian metro areas (Pune, Mumbai, Delhi, Bengaluru, Hyderabad, Chennai). If you query an unsupported global town, switch to `DISCOVERY_PROVIDER=mock`.
2. **Overture Maps S3 Availability**:
   - *Status*: Expected dependency.
   - *Detail*: Live discovery queries public Parquet files hosted on AWS S3 (`overturemaps-us-west-2`). If your local machine is offline or AWS S3 is unreachable, discovery will time out unless `DISCOVERY_PROVIDER=mock` is set.
3. **OpenRouter AI Gateway**:
   - *Status*: Expected dependency.
   - *Detail*: Uses the free model tier (`openrouter/free`). If OpenRouter experiences upstream rate limits or outages, set `AI_PROVIDER=mock` for instant offline criteria generation.
4. **Single-Node In-Process Workers**:
   - *Status*: Expected architectural decision.
   - *Detail*: Background search and crawler workers run asynchronously inside the FastAPI lifespan process. There is deliberately no Redis, Celery, or Kafka cluster.
5. **No CRM or Automated Outreach**:
   - *Status*: Strict product boundary.
   - *Detail*: Prospectra is an **Opportunity Queue & Evidence Workspace**. It does not send emails, dial phone numbers automatically, or manage CRM deals.

---

## PART 15 — "Do This Now" Practical Checklist

Print or follow this checklist as you perform your evaluation:

### Phase A: Start the Application
- [ ] Backend `.env` configured (with Supabase credentials and `DISCOVERY_PROVIDER`).
- [ ] Frontend `frontend/.env.local` configured.
- [ ] Backend running: `uvicorn backend.main:create_app --factory --port 8000 --reload`.
- [ ] Frontend running: `npm run dev` in `frontend/`.
- [ ] Open browser to `http://localhost:3000/`.

### Phase B: First-Time Account & Workspace
- [ ] Navigate to `/login`.
- [ ] Create a new seller account via Sign Up.
- [ ] Sign In with your new credentials.
- [ ] Create a new workspace (e.g., "Apex Web Studio").
- [ ] Verify you land on `/workspaces/[id]/prospects` showing the empty queue state.

### Phase C: Discover Prospects
- [ ] Click "Find Prospects Now".
- [ ] Enter pitch: "Modern Website Redesign & Online Ordering".
- [ ] Enter category: "Restaurants & Cafes".
- [ ] Enter city: "Pune".
- [ ] Click "Start Discovery & Scoring".
- [ ] Watch the 3-step live progress indicators.
- [ ] Verify modal closes and ranked prospects appear in the queue.

### Phase D: Evaluate & Inspect Queue
- [ ] Review priority score badges (e.g. `92%`, `80%`).
- [ ] Verify sorting: highest score is at the top.
- [ ] Test the live search filter (e.g. filter by "Bakery").
- [ ] Test min-score filter ($\ge 80\%$).
- [ ] Open the #1 ranked prospect's Detail Drawer.
- [ ] Check Outreach Action Bar (Email, Phone, WhatsApp, Website).
- [ ] Click "Copy Info" and verify clipboard content.

### Phase E: Inspect Evidence & Scoring
- [ ] Read the Qualification Rationale.
- [ ] Review the Factor Decomposition table (matched factors, points awarded).
- [ ] Review the Technical Evidence cards (Reachability, SSL, Viewport).
- [ ] Expand "View Raw Probe JSON" and verify technical transparency.
- [ ] Identify a prospect with no website and confirm it received the `no_website_opportunity` factor.

### Phase F: Record Human Decisions
- [ ] Approve prospect #1 for outreach.
- [ ] Add a seller note (e.g. "Called manager Rahul").
- [ ] Verify note autosaves ("Saving..." -> "Saved").
- [ ] Close drawer and verify table row shows `APPROVED` badge.
- [ ] Open prospect #2 and click Reject.
- [ ] Select a mandatory rejection reason from the dropdown.
- [ ] Switch to the "Rejected" tab and confirm prospect #2 is there.
- [ ] Switch back to "All Queue".

### Phase G: Export & Verify
- [ ] Click "Export Approved CSV" in the top bar.
- [ ] Download the CSV file.
- [ ] Open CSV in Excel / Sheets / Text editor.
- [ ] Confirm only approved prospects are included.
- [ ] Verify all 14 columns are populated accurately.
- [ ] Confirm your private seller note is present in the file.
