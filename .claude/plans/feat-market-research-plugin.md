# Market Research Plugin — Implementation Plan

## Context

The user needs a plugin to systematically find potential clients, extract their contact emails, and track the outreach pipeline status (new → contacted → responded → closed/not_interested). This plugin works alongside the existing GmailPlugin: market_research finds and stores prospects with emails, and the agent then uses GmailPlugin to actually send those emails. Outreach state must persist across conversations.

---

## Branch

`claude/market-research-plugin-zEjMo`

---

## File Structure

```
src/plugins/market_research/
├── __init__.py          # Re-export MarketResearchPlugin
├── plugin.py            # MarketResearchPlugin(Plugin) — thin wrapper
├── models.py            # Pydantic models + ProspectStatus enum
├── storage.py           # SQLite async CRUD via aiosqlite
└── service.py           # MarketResearchService + @tool definitions

tests/plugins/
└── test_market_research.py
```

**Files modified:**
- `src/plugins/__init__.py` — add market_research import
- `src/core/config.py` — add `TAVILY_API_KEY`

---

## Research Brief (ICP Document)

A human-readable Markdown file stored at `config.DATA_DIR / "market_research_brief.md"` that defines:
- What you're selling / your product's value prop
- Your ideal customer profile (company size, industry, geography, etc.)
- What signals indicate a good prospect
- Anything to avoid

This file is **automatically read** by `search_for_prospects` and `find_contact_email` to contextualize web searches and LLM-assisted evaluation. It can be updated any time — by you directly editing the file, or by asking the agent to update it.

Two additional tools manage this document:
- `get_research_brief()` — returns the current brief so the agent (or you) can review it
- `update_research_brief(content)` — overwrites the brief with new content; agent can call this when you say "update the brief to focus on X"

**Default brief** (written to disk on first `setup()` if the file doesn't exist):
```markdown
# Market Research Brief

## Product
[Describe what you are selling here]

## Ideal Customer Profile
- Industry: [e.g. SaaS, fintech, e-commerce]
- Company size: [e.g. 10-200 employees]
- Geography: [e.g. North America]
- Job titles to target: [e.g. CEO, Head of Operations]

## Good Prospect Signals
- [e.g. recently funded, hiring rapidly, uses competing tools]

## Avoid
- [e.g. enterprises over 1000 employees, non-profits]
```

---

## Data Model

### `ProspectStatus` (enum, stored as string)
`new` → `researching` → `contacted` → `responded` → `not_interested` → `closed`

### `Prospect` (Pydantic)
```python
class ProspectEmail(BaseModel):
    id: int
    email: str
    label: str | None       # "info", "sales", "ceo", etc.
    is_primary: bool
    source: str | None
    added_at: str

class Prospect(BaseModel):
    id: int
    company_name: str
    website: str | None
    contact_name: str | None
    industry: str | None
    emails: list[ProspectEmail] = []   # all known emails
    status: ProspectStatus = ProspectStatus.NEW
    notes: str | None
    source: str | None          # "manual", "web_search"
    last_contacted_at: str | None
    created_at: str
    updated_at: str

    @property
    def primary_email(self) -> str | None:
        for e in self.emails:
            if e.is_primary:
                return e.email
        return self.emails[0].email if self.emails else None
```

### SQLite Schema (`prospects.db` in `config.DATA_DIR`)
```sql
CREATE TABLE IF NOT EXISTS prospects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT NOT NULL,
    website         TEXT UNIQUE,          -- UNIQUE prevents duplicate site entries
    contact_name    TEXT,
    industry        TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    notes           TEXT,
    source          TEXT,
    last_contacted_at TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_company ON prospects(company_name COLLATE NOCASE);

-- One row per email address found; a prospect can have many
CREATE TABLE IF NOT EXISTS prospect_emails (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id     INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    label           TEXT,                 -- e.g. "info", "sales", "ceo", "support" — parsed from prefix
    is_primary      INTEGER NOT NULL DEFAULT 0,  -- 1 = this is the email used for outreach
    source          TEXT,                 -- "manual" | "web_search"
    added_at        TEXT NOT NULL,
    UNIQUE(prospect_id, email)            -- no duplicate emails per prospect
);
CREATE INDEX IF NOT EXISTS idx_emails_prospect ON prospect_emails(prospect_id);

-- Tracks every URL already visited during email/contact lookup so we never scrape the same page twice
CREATE TABLE IF NOT EXISTS visited_urls (
    url             TEXT PRIMARY KEY,
    visited_at      TEXT NOT NULL
);
```

**Multi-email logic:**
- `find_contact_email` extracts all emails from the page, stores each as a row in `prospect_emails`
- The first email added becomes `is_primary=1` automatically
- Duplicates (same email, same prospect) are silently ignored via the UNIQUE constraint
- When the agent uses the Gmail plugin to send an outreach email, it uses the row where `is_primary=1`
- User can say "use sales@co.com for prospect 3" → agent calls `update_prospect` which flips `is_primary`

---

## Tools (10 total)

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `get_research_brief` | — | Read the current ICP/product brief |
| `update_research_brief` | content | Overwrite the brief with new content |
| `add_prospect` | company_name, website?, contact_name?, email?, industry?, notes? | Manually add a prospect |
| `search_for_prospects` | query?, max_results=10 (hard cap: 25) | Web search (Tavily) for prospects; uses brief as context; skips duplicates; auto-adds new results |
| `list_prospects` | status?, limit=20 | List all or filtered-by-status prospects |
| `get_prospect` | prospect_id | Full details on one prospect |
| `update_prospect` | prospect_id, status?, contact_name?, notes?, last_contacted_at?, primary_email? | Update fields; `primary_email` flips which email is primary |
| `find_contact_email` | prospect_id | Web search; stores ALL found emails in `prospect_emails`; returns full list |
| `get_pipeline_summary` | — | Counts by status; shows contacted/responded/pending counts |
| `delete_prospect` | prospect_id | Remove a prospect from the list |

All tools return human-readable strings so the LLM can relay them to the user. Tools accessing the DB use `asyncio.run()` internally (LangChain `@tool` is sync; service has async methods called via `asyncio.run()`).

---

## Storage Layer (`storage.py`)

`ProspectStore` class using `aiosqlite`:
```python
class ProspectStore:
    def __init__(self, db_path: Path): ...
    async def initialize(self) -> None:              # CREATE TABLE IF NOT EXISTS (all 3 tables)
    async def add(self, **fields) -> Prospect:
    async def get(self, prospect_id: int) -> Prospect | None:   # JOINs prospect_emails
    async def list_all(self, status: str | None, limit: int) -> list[Prospect]:
    async def update(self, prospect_id: int, **fields) -> Prospect:
    async def add_email(self, prospect_id: int, email: str, label: str | None, source: str) -> ProspectEmail:
    async def set_primary_email(self, prospect_id: int, email: str) -> None:
    async def delete(self, prospect_id: int) -> bool:
    async def summary(self) -> dict[str, int]:       # {status: count}
    async def mark_url_visited(self, url: str) -> None:
    async def was_url_visited(self, url: str, ttl_days: int) -> bool:
```

---

## Web Research Strategy

**Pluggable search provider** — controlled by `MARKET_RESEARCH_SEARCH_PROVIDER` env var:

| Provider | Env var needed | LangChain class |
|----------|---------------|-----------------|
| `tavily` (default) | `TAVILY_API_KEY` | `TavilySearchResults` |
| `exa` | `EXA_API_KEY` | `ExaSearchResults` (via `langchain-exa`) |

A `SearchProvider` abstraction wraps both so the rest of the service doesn't care which is active. Graceful degradation when neither key is set.

**How each tool uses search:**
- `search_for_prospects`: reads the brief → builds a targeted query → calls provider → parses results → **deduplication check** (skip any URL already in `prospects.website` or `visited_urls`) → auto-adds new prospects only → returns: `"Found 8 results, added 5 new, skipped 3 already known"`
- `find_contact_email`: **checks `visited_urls` first** (skip if visited within TTL) → searches for `"{company} contact email site:{website}"` → Exa preferred here (better at targeted page retrieval); falls back to Tavily → extracts all emails via `re.findall` → stores each in `prospect_emails` → marks URLs visited

**Search caps:**
- `max_results` default: **10**, hard ceiling: **25** (clamped in code)
- Search call timeout: **10 seconds** per request
- `find_contact_email` visits at most **3 URLs per prospect** per call before giving up
- No re-scraping a URL visited within the last **7 days** (configurable via `MARKET_RESEARCH_URL_TTL_DAYS`)

---

## Config Addition (`src/core/config.py`)

Add inside `__init__`:
```python
# Market Research
self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
self.EXA_API_KEY = os.getenv("EXA_API_KEY", "")
self.MARKET_RESEARCH_SEARCH_PROVIDER = os.getenv("MARKET_RESEARCH_SEARCH_PROVIDER", "tavily")  # "tavily" | "exa"
self.MARKET_RESEARCH_MAX_RESULTS = int(os.getenv("MARKET_RESEARCH_MAX_RESULTS", "25"))          # hard cap
self.MARKET_RESEARCH_URL_TTL_DAYS = int(os.getenv("MARKET_RESEARCH_URL_TTL_DAYS", "7"))         # re-visit window
```

---

## Plugin Registration

`src/plugins/__init__.py`:
```python
import src.plugins.market_research.plugin  # noqa: F401
```

`src/plugins/market_research/__init__.py`:
```python
from src.plugins.market_research.plugin import MarketResearchPlugin  # noqa: F401
```

---

## Gmail Integration

The plugin exposes prospects with emails via `list_prospects` and `get_prospect`. When the user says "email this prospect", the agent:
1. Calls `get_prospect(id)` to retrieve email/contact name
2. Uses GmailPlugin's send tool to draft and send
3. Calls `update_prospect(id, status="contacted", last_contacted_at=now)` to mark outreach

No direct coupling needed — the LLM orchestrates between the two plugins.

---

## Tests (`tests/plugins/test_market_research.py`)

- `test_add_and_list_prospect` — add a prospect, verify it appears in list
- `test_update_status` — update status, verify DB reflects change
- `test_pipeline_summary` — multiple prospects, verify counts per status
- `test_delete_prospect` — delete, verify gone
- `test_get_research_brief_default` — brief file created with template on first access
- `test_update_research_brief` — write new content, verify file updated
- `test_find_email_no_tavily` — graceful message when no API key
- `test_search_prospects_no_tavily` — graceful message when no API key
- Use `tmp_path` fixture for isolated SQLite DB + brief file per test
- Mock `TavilySearchResults` for search tests

---

## Verification

1. Add plugin to `PLUGINS` env var: `PLUGINS="calendar,gmail,market_research"`
2. Ask agent: "Add prospect: Acme Corp, website acme.com, industry SaaS"
3. Ask agent: "List all prospects"
4. Ask agent: "Mark prospect 1 as contacted"
5. Ask agent: "Give me a pipeline summary"
6. (With Tavily key) Ask agent: "Search for B2B SaaS companies in fintech I could sell to"
7. Run `pytest tests/plugins/test_market_research.py -v`
8. Run `ruff check src/plugins/market_research/`
