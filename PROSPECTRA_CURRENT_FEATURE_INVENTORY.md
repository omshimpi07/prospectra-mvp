# Prospectra — Current Product Feature Inventory

**Repository**: `https://github.com/omshimpi07/prospectra-mvp.git`  
**Current Release**: Sprint 8 (`2528bed`)  
**Scope**: 100% Implemented User-Facing Functionality  

---

## A. Authentication

### 1. User Sign Up
- **Feature Name**: Email & Password Account Registration
- **Where it appears in UI**: `/login` (toggled via "Need an account? Sign Up")
- **What the user does**: Enters an email address and password (minimum 6 characters), then clicks "Sign Up".
- **What the system does**: Calls `supabase.auth.signUp({ email, password })` to provision a user identity in Supabase Auth.
- **What output the user should see**: A green alert message: *"Account created. Check your email or sign in directly."* The view toggles back to the Sign In state.
- **Important states**:
  - `loading`: Disables the submit button and renders a spinning `Loader2` indicator.
  - `error`: Displays a red alert banner with the error message from Supabase (e.g., *"User already registered"*, *"Password should be at least 6 characters"*).
- **Important limitations**: Relies on Supabase Auth email confirmation settings. If email confirmation is enabled in your Supabase project, the user must confirm before logging in; if disabled, they can log in immediately.

### 2. User Sign In
- **Feature Name**: Email & Password Session Sign In
- **Where it appears in UI**: `/login` (default state)
- **What the user does**: Enters registered email and password, then clicks "Sign In".
- **What the system does**: Calls `supabase.auth.signInWithPassword({ email, password })`. On success, Supabase stores session tokens in localStorage and the router navigates to `/`.
- **What output the user should see**: Page transitions to `/` (which redirects to the user's workspace or workspace creation view).
- **Important states**:
  - `loading`: Disables inputs and shows spinning loader.
  - `error`: Displays red alert box if credentials are invalid (e.g., *"Invalid login credentials"*).
- **Important limitations**: Session is persisted in browser client storage via Supabase Auth client. Only email/password auth is wired in the UI (OAuth is not configured).

---

## B. Workspace

### 1. Workspace Routing & Session Gate
- **Feature Name**: Authenticated Root Workspace Resolver
- **Where it appears in UI**: `/`
- **What the user does**: Visits the root URL `http://localhost:3000/`.
- **What the system does**: Verifies the active Supabase session. If no session exists, redirects to `/login`. If authenticated, queries `GET /api/v1/workspaces`. If 1+ workspaces exist, redirects automatically to `/workspaces/{workspaceId}/prospects`. If 0 workspaces exist, renders the inline Workspace Creator.
- **What output the user should see**: A brief "Entering Prospectra Workspace..." loader, followed by either immediate entry to their prospect queue or the "Welcome to Prospectra" setup screen.
- **Important states**:
  - `loading`: Centered spinner with *"Entering Prospectra Workspace..."*.
  - `error`: Displays error message if API fails to load workspaces.
- **Important limitations**: Automatic redirection always selects the first returned workspace (`wsList[0]`).

### 2. Inline Workspace Creator (First-Time User Setup)
- **Feature Name**: First-Time Workspace Provisioning
- **Where it appears in UI**: `/` (only when user has 0 workspaces)
- **What the user does**: Enters a workspace name (e.g., "Apex Digital Agency") and clicks "Create Workspace & Start".
- **What the system does**: Calls `POST /api/v1/workspaces` with `{ "name": "Apex Digital Agency" }`. Backend creates the workspace record, generates a URL slug, assigns the creator as owner in `workspace_members`, and returns the created workspace object.
- **What output the user should see**: Button shows a spinner, and on completion, routes directly to `/workspaces/{workspace.id}/prospects`.
- **Important states**:
  - `disabled`: Button is disabled when input is whitespace-only or when request is in flight.
  - `error`: Renders a red error banner if workspace creation fails.
- **Important limitations**: Does not provide a workspace deletion or multi-member invite UI in the frontend (though backend models support team members).

---

## C. Seller Intent / ICP (Ideal Customer Profile)

### 1. Guided Seller Intent Formulation
- **Feature Name**: Seller Pitch & Target Specification
- **Where it appears in UI**: Inside `FindProspectsModal` (accessible via "Find Prospects" buttons on `/workspaces/{workspaceId}/prospects`)
- **What the user does**: Enters their service offering (e.g., "Modern Website Redesign & Online Ordering"), target business category (e.g., "Restaurants & Cafes"), target city (e.g., "Pune"), and selects website presence preference.
- **What the system does**: Prepares seller intent payload to be structured and compiled via the backend ICP API.
- **What output the user should see**: Input form with validation, helper descriptions, and a "Start Discovery & Scoring" primary action button.
- **Important states**:
  - Default values pre-populated: Service Offering ("Modern Website Development & Online Ordering"), Category ("Restaurants & Cafes"), City ("Pune"), Candidate limit (20).
- **Important limitations**: Free-form pitch text is structured deterministically or via AI; if OpenRouter is unconfigured, fallback mock criteria is used.

### 2. ICP Compilation & Auto-Approval
- **Feature Name**: Structured ICP Generation & Activation
- **Where it appears in UI**: Stepper progress inside `FindProspectsModal`
- **What the user does**: Submits the form; compilation runs automatically in Step 1.
- **What the system does**: Calls `POST /api/v1/workspaces/{id}/icps` to create a draft, `POST .../compile` to generate structured criteria (canonical categories, target signals, negative keywords), and `POST .../approve` to activate the ICP.
- **What output the user should see**: Stage indicator highlights *"Structuring Seller Pitch"* with a spinner, followed by a green checkmark when complete.
- **Important states**:
  - `structuring`: Active spinner on Step 1.
  - `error`: Modal switches to error view with error description and a "Try Again" button.
- **Important limitations**: The modal auto-approves the compiled ICP to provide a seamless single-action flow for the seller rather than requiring manual schema verification.

---

## D. Prospect Discovery / Search

### 1. Spatial Discovery Execution
- **Feature Name**: Geospatial Business Search (Overture / DuckDB)
- **Where it appears in UI**: Step 2 inside `FindProspectsModal`
- **What the user does**: Watches progress indicator as the system queries open map data.
- **What the system does**: Calls `POST /api/v1/workspaces/{id}/searches` to queue a search, calls `POST .../run` to trigger DuckDB spatial bounding box extraction over Overture Places Parquet (or Mock provider), and polls `GET .../searches/{search_id}` until status is `COMPLETED`.
- **What output the user should see**: Stage indicator highlights *"Scanning Local Businesses"* with status text *"Querying business map data in [City]..."*.
- **Important states**:
  - `discovering`: In-process background query executing.
  - Polling interval: UI checks search completion every 1.5 seconds (up to 30 attempts).
- **Important limitations**: Spatial discovery is scoped to bounding box coordinates for supported Indian metropolitan areas (Pune, Mumbai, Delhi, Bengaluru, Hyderabad, Chennai) when using live Overture.

---

## E. Web Research

### 1. Technical Web Probe Pipeline
- **Feature Name**: Background Web Crawler & Signal Probe
- **Where it appears in UI**: Triggered during Step 3 of `FindProspectsModal`, inspectable in `ProspectDetailDrawer`
- **What the user does**: Triggered automatically when candidates are promoted to qualification.
- **What the system does**: Backend `ResearchWorker` claims queued candidates, uses `SecureWebFetcher` with anti-SSRF IP pinning to inspect public domains, measures HTTP status, SSL certificate validity, mobile viewport presence, CMS signatures, and extracts public contact info.
- **What output the user should see**: In modal: *"Qualifying Candidates & Scoring"*; in Drawer: detailed probe evidence logs.
- **Important states**:
  - `COMPLETED`: Domain successfully contacted and signals recorded.
  - `FAILED`: Domain unresolvable, timed out, or blocked by SSRF safeguards.
- **Important limitations**: Fetcher restricts page response size to 1 MB and adheres to a 10s maximum timeout to avoid hanging.

---

## F. Qualification

### 1. Deterministic Tri-State Rule Evaluation
- **Feature Name**: Algorithmic Signal Qualification
- **Where it appears in UI**:
  - Queue Table: Qualification status filter dropdown (`QUALIFIED`, `REVIEW_NEEDED`, `UNQUALIFIED`)
  - Detail Drawer: Header badge and "Algorithmic Qualification & Opportunity" card
- **What the user does**: Reviews system classification or filters the table by tier.
- **What the system does**: Compares extracted web signals against ICP requirements using rigid tri-state logic:
  - `QUALIFIED`: All required technical criteria explicitly confirmed.
  - `REVIEW_NEEDED`: One or more required signals are `UNKNOWN` (e.g., website unresolvable or missing).
  - `UNQUALIFIED` / `DISQUALIFIED`: Explicitly violates an exclusion or ICP filter.
- **What output the user should see**:
  - Badges: `QUALIFIED • Qualified Fit` (green), `REVIEW_NEEDED • Needs Human Review` (amber), `UNQUALIFIED • Not a Match` (slate).
  - Narrative: Plain-English explanation (e.g., *"High opportunity: active cafe missing mobile viewport."*).
- **Important states**: Never guesses missing data; strictly marks unknown signals as `REVIEW_NEEDED`.

---

## G. Scoring / Ranking

### 1. Multi-Factor ICP Opportunity Scoring
- **Feature Name**: Transparent Mathematical Priority Scoring
- **Where it appears in UI**:
  - Queue Table: Priority Score column (`ScoreBadge`)
  - Detail Drawer: Priority Score badge and "Factor Decomposition" table
- **What the user does**: Inspects numerical scores (0% to 100%) and factor breakdowns to understand ranking.
- **What the system does**: Selects scoring profile based on seller pitch (`WEB_REDESIGN_MODERNIZATION`, `MARKETING_AND_SEO`, or `GENERAL_B2B_SALES`), sums individual matched factor impacts (bounded $\le 1.00$), and multiplies by the qualification status multiplier (`1.0` for `QUALIFIED`, `0.60` for `REVIEW_NEEDED`, `0.0` for `UNQUALIFIED`).
- **What output the user should see**:
  - Score badge: Percentage badge color-coded (Emerald $\ge 80\%$, Amber $50-79\%$, Slate $< 50\%$).
  - Factor table: Shows factor name, status (`matched`, `unmatched`, `unknown`), impact points (`+0.25 / 0.25`), and technical evidence snippet.
- **Important states**:
  - Businesses with **no website** in web development profiles receive the `no_website_opportunity` factor (`+0.40 / 0.40`).
- **Important limitations**: Scoring is strictly mathematical and deterministic; no black-box LLM assigns arbitrary scores.

---

## H. Prospect Queue

### 1. Filterable & Sortable Workspace Table
- **Feature Name**: Deterministic Opportunity Queue
- **Where it appears in UI**: `/workspaces/{workspaceId}/prospects` (main content area)
- **What the user does**:
  - Switches Review Tabs: "All Queue", "Unreviewed", "Approved", "Rejected".
  - Filters by Min Score: All, $\ge 80\%$ (High), $\ge 65\%$ (Med+), $\ge 50\%$.
  - Filters by Qualification Tier: All, Qualified Fit, Needs Review, Not a Match.
  - Searches by text: Live search query matching business name, category, or city.
  - Clicks row: Opens the Prospect Detail Drawer.
- **What the system does**: TanStack Query fetches prospects from `GET /api/v1/workspaces/{id}/prospects` matching query params, cached and synchronized with URL search params.
- **What output the user should see**: Table displaying Priority Score, Business Name & Category, Core Opportunity summary, Contact Channel icons, Review Status badge, and Quick Action buttons.
- **Important states**:
  - `isLoading`: Centered spinner with *"Loading ranked prospects..."*.
  - `filteredProspects.length === 0`: Shows context-aware empty state (onboarding CTA if 0 prospects in workspace, reset filter button if filtered out).

---

## I. Prospect Detail / Explainability

### 1. Sliding Explainability Drawer
- **Feature Name**: Prospect Detail & Signal Drawer
- **Where it appears in UI**: Slide-over panel on `/workspaces/{workspaceId}/prospects?prospectId={id}`
- **What the user does**: Clicks any prospect row in the table to open; clicks "X" or backdrop to close.
- **What the system does**: Loads full prospect details, factor breakdowns, and lazily fetches technical evidence from `GET .../prospects/{id}/evidence`.
- **What output the user should see**:
  - Header: Business name, category tag, city, priority score badge.
  - Direct Human Outreach bar: Email, Call, WhatsApp, Website quick links, and "Copy Info" button.
  - Human Seller Decision card: Approve, Reject, Reset buttons, rejection reason dropdown, seller note textarea.
  - Algorithmic Qualification card: Status badge, human explanation, factor decomposition list.
  - Audit Trail card: Visual probe cards for HTTP reachability, SSL certificate, mobile viewport, with collapsible raw JSON toggle.
- **Important states**:
  - Synchronized with URL param `?prospectId=UUID` allowing direct bookmarking and browser back/forward navigation.

---

## J. Human Review

### 1. Review Decision State Transitions
- **Feature Name**: Human Review Status Controls
- **Where it appears in UI**:
  - Inline Table: Quick Approve (green checkmark) and Quick Reject (rose X) buttons.
  - Detail Drawer: "Approve for Outreach", "Reject", and "Reset" buttons.
- **What the user does**: Clicks Approve to qualify for outreach, Reject to pass, or Reset to return to Unreviewed.
- **What the system does**: Calls `PATCH /api/v1/workspaces/{id}/prospects/{prospectId}/review` with `{ review_status }`. Updates cache optimistically and invalidates query.
- **What output the user should see**: Badge updates immediately; review metadata updates with timestamp.
- **Important states**:
  - `APPROVED`: Marked for outreach and default inclusion in CSV export.
  - `REJECTED`: Mandatory rejection reason required; excluded from default CSV export.
  - `UNREVIEWED`: Initial state after automated scoring.

### 2. Structured Rejection Reasons
- **Feature Name**: Mandatory Rejection Reason Selector
- **Where it appears in UI**: Inside `ProspectDetailDrawer` when "Reject" is selected
- **What the user does**: Selects a reason from the dropdown:
  - "Not a fit for our niche/offering"
  - "Business appears closed or inactive"
  - "Inaccurate or missing contact channels"
  - "Already existing client or in progress"
  - "Poor gap opportunity / unviable prospect"
  - "Other / custom reason"
- **What the system does**: Persists `rejection_reason` along with `review_status = "REJECTED"`.
- **What output the user should see**: Selected reason is saved to the backend; if user switches to Approved or Reset, `rejection_reason` is automatically cleared.

---

## K. Seller Notes

### 1. Private Qualitative Seller Notes
- **Feature Name**: Autosaving Seller Context Notes
- **Where it appears in UI**: Inside `ProspectDetailDrawer` under Human Seller Decision
- **What the user does**: Types notes into the textarea (up to 1,000 characters), e.g., *"Spoke to manager Rahul, owner visits on Thursdays."*
- **What the system does**: Debounces keystrokes for 600ms, then sends `PATCH .../review` with the note.
- **What output the user should see**:
  - Live character counter: `X / 1000`.
  - Save indicator: Shows "Saving..." with spinner, then green "Saved" with checkmark, then fades.
- **Important states**:
  - `saving` -> `saved` -> `idle`.
  - Error state displayed if API call fails.

---

## L. Export

### 1. Formula-Injection-Safe CSV Export
- **Feature Name**: Export Approved CSV
- **Where it appears in UI**: Top navigation bar button ("Export Approved CSV") on `/workspaces/{workspaceId}/prospects`
- **What the user does**: Clicks the export button.
- **What the system does**: Calls `GET /api/v1/workspaces/{id}/prospects/export?review_status=...`. Streams an RFC 4180 CSV file with headers and triggers a browser download.
- **What output the user should see**: Button shows a loading spinner during export; browser downloads a file named `prospects_{workspace_id[:8]}_{status}_{timestamp}.csv`.
- **What data is included**: 14 columns: Business Name, Canonical Category, City, Website, Priority Score, Scoring Profile, Qualification Status, Human Review Status, Core Opportunity, Public Email, Phone, Rejection Reason, Seller Note, Discovered At.
- **Security protections**: Cells starting with formula characters (`=`, `+`, `-`, `@`, `\t`, `\r`) are automatically escaped with a leading single quote (`'`) to neutralize CSV formula injection attacks in Excel and Sheets.
- **Important limitations**: Default export filters to `review_status = APPROVED` (or respects active tab filter if not "All Queue").

---

## M. Error / Loading / Empty States

### 1. Context-Aware Queue Empty States
- **Feature Name**: Smart Queue Empty State
- **Where it appears in UI**: Prospect table container
- **What the user does**: Views queue when no prospects are available.
- **What the system does**: Checks total prospects in workspace vs. filtered prospects.
- **What output the user should see**:
  - If workspace has 0 prospects: Prominent card with *"No prospects in this workspace yet"* and a primary **"Find Prospects Now"** button.
  - If filters exclude all prospects: *"No prospects match your current criteria"* with a **"Reset all filters"** link.

### 2. Global Error Alerts & Spinners
- **Feature Name**: Visual Error & Loading Feedback
- **Where it appears in UI**: Across all views (login, root, workspace, modal, drawer)
- **What the user does**: Sees feedback when network or server issues occur.
- **What the system does**: Catches API exceptions and displays user-friendly error banners with retry options.
- **What output the user should see**: Rose/red alert banners with message text and "Retry" buttons where applicable.

---

## N. Other Implemented Features

### 1. Contact & Outreach Fast Actions
- **Feature Name**: Direct Communication Links
- **Where it appears in UI**:
  - Table: `ContactChannels` icon row (Globe, Phone, Mail indicators).
  - Detail Drawer: Outreach Action Bar buttons (Email, Call, WhatsApp, Website, Copy Info).
- **What the user does**: Clicks any available channel.
- **What the system does**:
  - Email: Opens default mail client via `mailto:{email}?subject=...`
  - Call: Triggers device phone dialer via `tel:{phone}`
  - WhatsApp: Opens WhatsApp Web/app via `https://wa.me/{sanitized_phone}`
  - Website: Opens external link in new tab with `rel="noopener noreferrer"`
  - Copy Info: Formats business name, website, email, phone, and opportunity summary into clipboard text.
- **What output the user should see**: "Copied" confirmation on clipboard copy; immediate handoff to communication app.
- **Important limitations**: If a channel is absent from crawler evidence, the corresponding button renders as a disabled grayed-out indicator (e.g., *"No WhatsApp"*).
