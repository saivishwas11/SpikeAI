## SpikeAI Analytics & SEO Backend – Hackathon Submission

This repository implements a **production-ready AI backend** for the Spike AI Builder Hackathon.  
The system answers **natural-language questions** about:

- **Web Analytics (GA4)**
- **SEO Audits (Screaming Frog → Google Sheets)**

It exposes **one HTTP POST API** that performs **agent-based reasoning** via an orchestrator and is designed to be:

- **Evaluator-safe** (works with evaluator-provided `credentials.json` and `propertyId`).
- **Extensible** to new agents and domains.
- **Headless** (no UI – API only).

---

## 1. High-Level Architecture

### 1.1 Components Overview

- **API Layer (`main.py`)**

  - FastAPI app exposing a single endpoint: `POST /query` on port **8080**.
  - Accepts a natural-language `query` and an optional GA4 `propertyId`.
  - Handles HTTP-level concerns (validation, error translation, health checks).

- **Orchestrator (`orchestrator.py`)**

  - Central decision-maker:
    - **Intent detection** – Analytics vs SEO vs (future) domains.
    - **Agent routing** – Decides which agent(s) to call.
    - **Task decomposition** – Breaks complex queries into sub-queries when needed.
    - **Response aggregation** – Merges multi-agent responses into a final answer.
  - Uses the **LiteLLM-backed LLM** (via `utils/llm.py` / `utils/llm_utils.py`) for reasoning and planning.

- **Analytics Agent (`agents/analytics_agent.py`) – Tier 1**

  - Connects to **Google Analytics 4 (GA4) Data API** using:
    - `credentials.json` at **repository root** (service account).
    - `propertyId` passed in the API request.
  - Responsibilities:
    - Interpret the user query into a **GA4 reporting plan**:
      - Metrics, dimensions, date ranges, filters, ordering.
    - Validate fields against an **allowlist** for safety and GA4 compatibility.
    - Execute live GA4 Data API requests.
    - Handle empty or sparse datasets.
    - Return both **structured data** and **natural-language explanation**.

- **SEO Agent (`agents/seo_agent.py`) – Tier 2**

  - Works on top of **Screaming Frog exports stored in Google Sheets**.
  - Uses the `utils/sheets.py` + `utils/google_sheets_service.py` and `utils/ga4_schema.py/ga4_planner.py` stack to:
    - **Load SEO data** from the provided Google Sheet (live, not static CSV).
    - Perform filtering, grouping, aggregation, and conditional logic.
    - Handle schema changes gracefully (e.g., new/renamed columns).
    - Provide both **structured JSON** and **LLM-generated summaries**.

- **Shared Models (`models.py`)**

  - Pydantic models for:
    - `QueryRequest` – input contract for `/query`.
    - `QueryResponse` – unified output, wrapping agent results + explanations.

- **Utilities (`utils/`)**
  - `auth.py` – GA4 authentication helpers using `credentials.json`.
  - `llm.py`, `llm_utils.py` – LLM client using the **LiteLLM proxy** at `http://3.110.18.218`.
  - `ga4_planner.py`, `ga4_schema.py` – mapping between natural language and GA4 metrics/dimensions.
  - `sheets.py`, `google_sheets_service.py` – Google Sheets access for SEO data.

### 1.2 Textual Architecture Diagram

Logical flow (simplified text diagram):

```text
Client (Evaluator)
    |
    |  POST /query  { query, propertyId? }
    v
FastAPI API Layer (main.py)
    |
    v
Orchestrator (orchestrator.py)
    |--[Intent Detection via LLM]--------------------------.
    |                                                     |
    |                              .----------------------'
    |                              |
    |                 +------------+------------+
    |                 |                         |
    v                 v                         v
Analytics Agent   SEO Agent            (Future Agents / Domains)
(GA4 Data API)    (Sheets + SFrog)     e.g., CRM, Ads, etc.
    |                 |
    v                 v
Structured data + explanations
    |
    v
Orchestrator aggregates & formats
    |
    v
FastAPI returns JSON response to client
```

---

## 2. API Contract

### 2.1 Endpoint

- **Method**: `POST`
- **URL**: `http://localhost:8080/query`

### 2.2 Request: GA4 (Analytics) Queries

For **GA4-only** queries, `propertyId` is **required**:

```json
{
  "propertyId": "<GA4_PROPERTY_ID>",
  "query": "Give me a daily breakdown of page views, users, and sessions for the /pricing page over the last 14 days and summarize trends."
}
```

### 2.3 Request: SEO-Only Queries

For non-GA4 queries (e.g., SEO-only), `propertyId` may be omitted:

```json
{
  "query": "Which URLs do not use HTTPS and have title tags longer than 60 characters?"
}
```

### 2.4 Response (Conceptual)

`QueryResponse` (simplified conceptual schema – see `models.py` for exact details):

```json
{
  "answer": "Natural-language explanation of the result.",
  "analytics": {
    "raw": {
      "rows": [
        /* GA4 rows */
      ],
      "metadata": {
        /* metrics/dimensions */
      }
    },
    "summary": "Optional GA4-specific explanation"
  },
  "seo": {
    "raw": [
      /* SEO rows / aggregations */
    ],
    "summary": "Optional SEO-specific explanation"
  },
  "debug": {
    "intent": "analytics|seo|multi",
    "plan": {
      /* GA4 plan or SEO filters/grouping */
    },
    "agents_used": ["analytics", "seo"]
  }
}
```

The system can also return **strict JSON** when requested in the user prompt (e.g., “return in JSON only”).

---

## 3. Deployment & Execution

### 3.1 Execution Requirements (Hackathon-Ready)

This project satisfies the required constraints:

- **Port**: The app binds **only to port 8080** (see `main.py`).
- **deploy.sh**: A `deploy.sh` script exists at the **repository root** and is the **single entrypoint**.
- **Virtual environment**: If created, the venv is at the repository root as **`.venv`**.
- **GA4 credentials**: A valid `credentials.json` file is expected at the **project root**.
  - Evaluators can replace this file and provide their own `propertyId` without code changes.

### 3.2 `deploy.sh` Responsibilities

`deploy.sh` (root) performs:

1. **Project root resolution**
   - Ensures all imports (`agents`, `utils`, etc.) work correctly.
2. **Python detection**
   - Prefers `python3`, falls back to `python`.
3. **Virtual environment management**
   - Creates `.venv` if missing.
   - Activates `.venv` from the root.
4. **Dependency installation**
   - Upgrades `pip`.
   - Installs `requirements.txt`.
5. **Server startup**
   - Runs `python main.py` (which:
     - Initializes SEO agent (data load).
     - Starts Uvicorn on `0.0.0.0:8080`).
   - Long-running server process is started via an `exec` call.

Evaluators can run:

```bash
bash deploy.sh
```

Within 7 minutes, dependencies install and the **server is ready** for requests.

---

## 4. Setup Instructions

### 4.1 Prerequisites

- **Python**: 3.10+ recommended.
- **bash**: for running `deploy.sh`.
- **Google Cloud project** with GA4 Data API, Admin API enabled.
- **Google Analytics 4 property**.
- **Service account** with access to the GA4 property.
- **LiteLLM key** provided by Spike AI (`sk-...`) and base URL `http://3.110.18.218`.
- **Google Sheet** URL for Screaming Frog export (provided).

### 4.2 GA4 Setup (Credentials and Property)

Follows the hackathon instructions (summarized):

1. Create a project in **Google Cloud Console**.
2. Create a **service account** under that project.
3. Generate a **JSON key** for the service account.
4. Save that file as **`credentials.json` at the repository root**.
5. In **Google Analytics**:
   - Create an account + GA4 property.
   - In Admin → Account access management, add the **service account email** as a user.
   - Copy the **GA4 `propertyId`**.
6. Enable APIs in GCP:
   - Google Analytics Admin API.
   - Google Analytics API.
   - Google Analytics Data API.

> During evaluation, `credentials.json` and `propertyId` will be replaced by the evaluators.  
> The system is built to use them dynamically, with **no code changes required**.

### 4.3 LLM / LiteLLM Configuration

Set the following environment variables (e.g., in `.env` at project root):

- `LITELLM_API_KEY=sk-...` – The key you received via email.
- `LITELLM_BASE_URL=http://3.110.18.218`

The **LLM client** (`utils/llm.py`) uses these values to route all reasoning calls via the LiteLLM proxy to Google models (e.g., `gemini-2.5-flash`, `gemini-3-pro-preview`, `gemini-2.5-pro`).

### 4.4 SEO / Screaming Frog Sheet Configuration

Set environment variables (example – adapt to your utils):

- `SEO_SHEET_ID` – The ID of the Google Sheet provided (`1zzf4ax_H2WiTBVrJigGjF2Q3Yz-qy2qMCbAMKvl6VEE`).
- `SEO_SHEET_RANGE` – Default range or tab (e.g., `Raw!A:Z`), depending on implementation in `utils/sheets.py`.

The SEO agent (`agents/seo_agent.py`) uses `load_seo_data()` from `utils/sheets.py`, which:

- Connects to Google Sheets using the same or dedicated credentials.
- Loads the Screaming Frog export into a **pandas DataFrame**.

### 4.5 Running Locally

```bash
chmod +x deploy.sh
bash deploy.sh
```

Once the server is up:

- Health check:

```bash
curl http://localhost:8080/health
```

- Example GA4 query:

```bash
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{
    "propertyId": "123456789",
    "query": "Give me a daily breakdown of page views, users, and sessions for the /pricing page over the last 14 days and summarize trends."
  }'
```

- Example SEO query:

```bash
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which URLs do not use HTTPS and have title tags longer than 60 characters?"
  }'
```

---

## 5. Agent Behaviors & Reasoning

### 5.1 Analytics Agent (GA4) – Tier 1

**Input**: User query + `propertyId`.  
**Output**: GA4 data + explanation.

Steps:

1. **Intent parsing**
   - Extract:
     - Metrics: e.g., `screenPageViews`, `totalUsers`, `sessions`.
     - Dimensions: e.g., `date`, `pagePath`, `sessionSourceMedium`.
     - Date range: e.g., “last 14 days”.
     - Filters: e.g., `/pricing` page.
2. **Reporting plan construction**
   - Validates metrics/dimensions against an **allowlist** defined in `utils/ga4_schema.py` to avoid invalid API combinations.
3. **GA4 Data API call**
   - Uses service account credentials from `credentials.json` via `utils/auth.py`.
   - Builds a `RunReportRequest` for the `propertyId`.
4. **Post-processing**
   - Handles:
     - Empty datasets.
     - Sparse data.
     - Time-series vs aggregate queries.
   - Returns:
     - Structured rows with metric/dimension names.
     - LLM-generated natural-language explanation of trends.

### 5.2 SEO Agent – Tier 2

**Input**: Natural language SEO question.  
**Output**: Filtered rows / aggregates + explanation.

Steps:

1. **Data loading**
   - `load_seo_data()` reads the Screaming Frog sheet into a DataFrame.
   - Handles columns like URL, protocol, title length, indexability, etc.
2. **Query planning**
   - LLM maps query to:
     - Filter conditions (e.g., protocol != https, title_length > 60).
     - Grouping (e.g., by indexability).
     - Aggregations (e.g., counts, percentages).
3. **Execution**
   - Performs DataFrame transformations.
   - Deals with **schema changes** by:
     - Looking up columns dynamically.
     - Being tolerant to missing / extra columns.
4. **Output**
   - Returns:
     - Structured JSON rows or aggregates.
     - Explanation (e.g., “X% of pages are indexable, which is average…”).

### 5.3 Multi-Agent Orchestration – Tier 3

For queries requiring both analytics and SEO:

1. **Intent Detection**
   - LLM identifies that both GA4 and SEO data are needed (e.g., “top 10 pages by views and their title tags”).
2. **Routing**
   - Calls Analytics Agent first to get top URLs by views.
   - Calls SEO Agent with those URLs to get title tags / indexability.
3. **Fusion**
   - Joins results on page URL or path.
   - Produces a unified response (table-like structure + explanation).

---

## 6. Error Handling & Robustness

- **GA4 Errors**

  - Invalid metrics/dimensions: blocked by allowlist validation.
  - Missing/invalid `propertyId`: returns 4xx with helpful message.
  - Empty datasets: returns a friendly explanation rather than crashing.

- **SEO / Sheets Errors**

  - Sheet unreachable: returns 5xx with diagnostic info.
  - Schema mismatch: attempts to adapt; clearly documents missing columns.

- **LLM / LiteLLM Errors**
  - 429 (rate limit): exponential backoff logic (recommended) to be used in client helpers.
  - Budget exhaustion: clear error surfaced to caller when LiteLLM rejects calls.

---

## 7. Assumptions & Open Questions

### 7.1 Assumptions

- `credentials.json` at the root is always **valid for GA4 Data API** and has access to the provided `propertyId`.
- The provided Screaming Frog sheet remains accessible and its ID remains stable.
- Date ranges in natural language (e.g., “last K days”) are interpreted using the system clock in UTC.
- Evaluators will not require authentication on the `/query` endpoint (public for hackathon).

### 7.2 Open Questions / Future Work

- Authentication / authorization for the API in a real production environment (e.g., API keys, OAuth).
- More advanced observability: tracing per-agent execution, structured logging, APM integration.
- Explicit schema versioning for Screaming Frog exports.
- More agents: Ads spend, CRM, revenue, etc., plugged into the same orchestrator.

---

## 8. Testing Strategy

> Note: Tests can be expanded, but the strategy and main test cases per tier are defined here.

### 8.1 Tier 1 – Analytics Agent Test Cases

1. **Daily Metrics Breakdown**
   - Query: “Give me a daily breakdown of page views, users, and sessions for the /pricing page over the last 14 days. Summarize any noticeable trends.”
   - Expectation: Valid GA4 call with date dimension, metrics, and `/pricing` filter; trend explanation.
2. **Traffic Source Analysis**
   - Query: “What are the top 5 traffic sources driving users to the pricing page in the last 30 days?”
   - Expectation: GA4 plan uses a source/medium dimension, sorted by users or sessions.
3. **Calculated Insight**
   - Query: “Calculate the average daily page views for the homepage over the last 30 days. Compare it to the previous 30-day period and explain whether traffic is increasing or decreasing.”
   - Expectation: Two date ranges, comparison, and reasoning sentence.

### 8.2 Tier 2 – SEO Agent Test Cases

1. **Conditional Filtering**
   - Query: “Which URLs do not use HTTPS and have title tags longer than 60 characters?”
2. **Indexability Overview**
   - Query: “Group all pages by indexability status and provide a count for each group with a brief explanation.”
3. **Calculated SEO Insight**
   - Query: “Calculate the percentage of indexable pages on the site. Based on this number, assess whether the site’s technical SEO health is good, average, or poor.”

### 8.3 Tier 3 – Multi-Agent Test Cases

1. **Analytics + SEO Fusion**
   - Query: “What are the top 10 pages by page views in the last K days, and what are their corresponding title tags?”
2. **High Traffic, High Risk**
   - Query: “Which pages are in the top 20% by views but have missing or duplicate meta descriptions? Explain the SEO risk.”
3. **Cross-Agent JSON Output**
   - Query: “Return the top 5 pages by views along with their title tags and indexability status in JSON format.”

---

## 9. Production Readiness & Extensibility

- **Production Readiness**

  - Clear deployment entrypoint (`deploy.sh`) and environment management (`.venv`).
  - Strong separation of concerns: API vs orchestrator vs agents vs utilities.
  - Externalized secrets (`credentials.json`, LiteLLM API key, sheet IDs).

- **Extensibility**
  - New agents can be added under `agents/` and plugged into `orchestrator.py`.
  - GA4 schema & allowlists are centralized in `utils/ga4_schema.py`.
  - SEO data access is abstracted in `utils/sheets.py`, so changing the sheet or adding new tabs is straightforward.

This documentation is intended to be **submission-ready** for the Spike AI Builder Hackathon and describes the full technical architecture, setup, assumptions, and behavior of the system.
