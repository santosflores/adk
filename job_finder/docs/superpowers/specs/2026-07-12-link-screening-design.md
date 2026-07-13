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
