# Link-screening step — design

**Date:** 2026-07-12
**Status:** Approved, pending implementation plan
**Project:** `job_finder/`

## Problem

Some links that reach the Sheets export are **dead** (404/gone) or for the
**wrong locale** (a job in a country the user isn't targeting). We want a step
that follows each link, reads the page, and keeps only live, in-locale posts.

## Decisions (from brainstorming)

| Question | Decision |
| --- | --- |
| Disposition of rejected posts | **Drop** — only live, in-locale posts reach the Sheet |
| Locale definition | **Configured target country + always-keep-remote** (`TARGET_LOCALE` in `.env`) |
| Fetch/read mechanism | **HTTP fetch + parse structured data** (deterministic; no LLM) |
| Live but location undeterminable | **Keep** (conservative — never drop a possibly-good post) |
| Network error / timeout | **Drop** (treated as dead — a link that won't load for us likely won't for the user) |
| Shared vs per-vendor parsing | **Shared** JSON-LD classifier — schema.org `JobPosting` is a real shared *contract*, unlike the coincidental URL shapes the per-ATS `extract_*_link` extractors handle |

## Where it fits

New node `screen_node`, inserted between `collect_posts` and `export_node`.

```
collect_posts ── screen_node ── export_node
```

Edge change in `agent.py`: replace `(collect_posts, export_node)` with
`(collect_posts, screen_node)` and `(screen_node, export_node)`.

`screen_node` takes the deduped `list[dict]` (`{title, url, snippet, id}`),
follows each `url`, and yields only survivors. `export_node` is unchanged — it
still writes whatever list it receives.

## Pure logic (`tools/main.py`)

Framework-free, network-free, fast-tier (no `google.*`), TDD'd one at a time.

- `is_dead(status_code: int) -> bool`
  `True` for 404, 410, and `>= 500`, plus a `0` sentinel the glue uses for
  network errors/timeouts. `200` and other 2xx/3xx are not dead.

- `location_matches(location: str, target: str) -> bool`
  `True` if `target` appears in `location` (case-insensitive), **or** the
  location is remote (`remote` / `anywhere` / `worldwide`). This is where the
  "remote-OK" rule lives.

- `extract_job_location(html: str) -> str | None`
  Find the `application/ld+json` block containing a `JobPosting` and return its
  `jobLocation` address text. `None` if there is no JSON-LD, no `jobLocation`,
  or the JSON is malformed.

- `should_keep(status_code: int, html: str, target: str) -> bool`
  Composition / single decision point:
  - dead (`is_dead`) → `False`
  - else location unknown (`extract_job_location(html) is None`) → `True` (keep)
  - else → `location_matches(location, target)`

## Glue (`agent.py`) — verified via `adk web`, not unit-tested

`screen_node` (async):
- Reads `TARGET_LOCALE`; if missing, `yield` a visible error Event (a generator
  node that `return`s / yields `None` is a silent dead-end — per the ADK gotchas).
- Fetches every post `url` concurrently with a bounded `asyncio.Semaphore` (e.g.
  10) using an async `httpx` client. Each fetch returns `(status_code, text)`;
  any exception/timeout maps to `(0, "")`.
- Keeps posts where `should_keep(status_code, text, TARGET_LOCALE)` is `True`.
- `yield Event(output=survivors)`.

## Config & dependencies

- `.env`: `TARGET_LOCALE` (e.g. `US`, `Mexico`). Read in `agent.py`.
- `requirements.txt`: add `httpx` (async HTTP client) — a real runtime dep.

## Error handling

| Situation | Result |
| --- | --- |
| 404 / 410 / 5xx | dead → drop |
| Network error / timeout | sentinel `0` → dead → drop |
| Live, location parseable, out of locale | drop |
| Live, location parseable, in locale or remote | keep |
| Live, location undeterminable | keep |
| `TARGET_LOCALE` missing | error Event (no silent dead-end) |

## Testing plan

One case per decision the code makes (branches, not type richness):

- `is_dead`: `200` keep; boundary `500` dead; `404` dead; sentinel `0` dead.
- `location_matches`: target match; no match; each remote synonym; case-insensitivity.
- `extract_job_location`: has JSON-LD with location; no `<script>` block;
  malformed JSON; `JobPosting` present but no `jobLocation`.
- `should_keep`: composition matrix (dead / unknown-location / in-locale /
  out-of-locale / remote).

Real ATS HTML captured to fixtures during Red (see one live sample per vendor).

**Build order (TDD reps):** `is_dead` → `location_matches` →
`extract_job_location` → `should_keep`, then wire `screen_node`.

## Open / deferred

- If Red reveals a vendor does **not** emit schema.org JSON-LD, fall back to a
  per-vendor location extractor for that vendor only (keep the shared path for
  the others).
- Timeout is treated as dead (drop). Revisit if it drops too many transiently-
  slow but live links.

---

## Amendment 2026-07-13 — mechanism pivot: JSON-LD → ATS JSON APIs

**Trigger:** before implementing the parse step, we probed one live page per ATS
(the "capture a real fixture in Red" step, done early to de-risk). The
shared-JSON-LD assumption did not survive contact with reality.

### What the probe found

| ATS | JSON-LD in raw HTML? | `jobLocationType` | country in JSON-LD |
| --- | --- | --- | --- |
| Ashby (openai) | present | — | `jobLocation` present |
| Lever (palantir) | present | `None` | `addressCountry` **null** (only `"Palo Alto, CA"`) |
| Greenhouse (discord, hosted board) | **0 blocks** | — | absent |

Three fatal problems for the JSON-LD plan: Greenhouse emits **no** JSON-LD on its
hosted board; `jobLocationType` is unreliable (Lever leaves it null); and
`addressCountry` is often null, forcing fuzzy free-text country matching.

By contrast the **public ATS JSON APIs** — reachable from the `id` we already
extract plus the company slug (`parts[3]` of the URL in all three ATSes) — return
clean, structured data:

| ATS | endpoint | country | remote signal | dead |
| --- | --- | --- | --- | --- |
| Lever | `api.lever.co/v0/postings/{co}/{id}` | `country: "US"` | `workplaceType: "remote"/"hybrid"/"on-site"` | 404 |
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{co}/jobs/{id}` | `offices[].location` (has country) / `location.name` | text in `location.name` (e.g. `"… (Remote (U.S.))"`) | 404 |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{co}` (board-level list) | `address.postalAddress.addressCountry: "United States"` | `isRemote` | `id` absent from list |

### Decision

**Pivot the mechanism to the ATS JSON APIs (revives the rejected Approach C).**
The only cost of Approach C in brainstorming ("3 more endpoints") is outweighed
now that the HTML path is demonstrably broken. The APIs also make the pure layer
*easier* to test (JSON dict in → decision out, no HTML scraping) and finally give
a real remote/hybrid/on-site field — the structured "type" the user wanted.

### Revised mechanism

- **Fetch (glue, per-vendor):** build the API URL from `id` + company slug.
  Lever / Greenhouse are single-job-by-id (404 = dead). Ashby is board-level:
  fetch the board once per company, and `id`-not-in-list = dead. Dedupe companies
  so Ashby is one call per company, not per post.
- **HTTP status → deadness** still via `is_dead` (unchanged, already built).
  Ashby "id absent" maps to a dead sentinel in the glue.

### Revised pure layer (`tools/main.py`)

- `is_dead(status_code)` — **unchanged, already implemented and committed.**
- Per-vendor field extractors (house-style duplication, like `extract_*_link`),
  each mapping that vendor's JSON to a normalized `(country: str | None,
  is_remote: bool)`:
  - `extract_lever_fields(job: dict) -> tuple[str | None, bool]`
  - `extract_greenhouse_fields(job: dict) -> tuple[str | None, bool]`
  - `extract_ashby_fields(job: dict) -> tuple[str | None, bool]`
- `location_matches(country: str, target: str) -> bool` — **simplified**:
  case-insensitive substring of `target` in `country`. The remote-synonym branch
  is **removed** (remote is now a structured bool, not scraped from text).
- `should_keep(status_code: int, country: str | None, is_remote: bool, target:
  str) -> bool` — dead → drop; `is_remote` → keep; `country is None` → keep
  (unknown → keep, unchanged decision); else `location_matches(country, target)`.

### New open / deferred

- **Country representation mismatch:** Lever returns ISO (`"US"`), Ashby returns
  full name (`"United States"`), Greenhouse returns free text. A `TARGET_LOCALE`
  of `"Mexico"` won't substring-match Lever's `"MX"`. Deferred — surface per
  vendor with real fixtures; a small alias map or multi-form target is the fix.
- The original JSON-LD reps (`extract_job_location`) are **dropped** in favor of
  the per-vendor API extractors above.
