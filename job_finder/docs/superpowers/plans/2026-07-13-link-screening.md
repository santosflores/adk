# Link-Screening Step Implementation Plan

> **Tutoring mode (this repo's override):** This plan is a **coaching roadmap**, not a
> copy-in spec. Each rep lists its files, interface contract, and the exact **test cases**
> (inputs → expected — the design decisions). **You** write the pytest code and the
> implementation during Red → Green → Refactor coaching; I don't implement for you unless
> asked. Steps use checkbox (`- [ ]`) syntax so we can track them.

**Goal:** Add a step that follows each collected link, reads the page, and keeps only live,
in-locale (or remote) job posts before they reach the Sheets export.

**Architecture:** Four pure, network-free helpers in `tools/main.py` (TDD'd fast-tier), composed
by `should_keep`. A thin async glue node `screen_node` in `agent.py` fetches every post URL
concurrently and filters with `should_keep`. Inserted between `collect_posts` and `export_node`.

**Tech Stack:** Python 3.14 (`.venv/`), pytest 9.0.3, `httpx` (new async HTTP dep), google-adk 2.2.0.

## Global Constraints

- Run tests via the venv: `.venv/bin/python -m pytest job_finder/tools/ -v` (from workspace root).
- **No `google.*` / `google.genai` imports in `tools/main.py`** — keeps the fast tier warning-free.
- Pure helpers: framework-free **and** network-free (they take already-fetched `html`/`status_code`).
- Test style: parametrized, `from .main import ...`, one assertion per test (see `test_is_confident.py`).
- Every test must be **seen to fail once** before implementing (stub with a deliberately *wrong*
  value so skip/false paths can't pass vacuously).
- Nodes are thin adapters — **not** unit-tested; verify glue via `adk web`.
- Design source: `docs/superpowers/specs/2026-07-12-link-screening-design.md`.

**Build order:** `is_dead` → `location_matches` → `extract_job_location` → `should_keep` → wire `screen_node`.

---

## File Structure

- `job_finder/tools/main.py` — add the 4 pure helpers.
- `job_finder/tools/test_is_dead.py` — new test file (rep 1).
- `job_finder/tools/test_location_matches.py` — new (rep 2).
- `job_finder/tools/test_extract_job_location.py` — new (rep 3).
- `job_finder/tools/test_should_keep.py` — new (rep 4).
- `job_finder/tools/__init__.py` — export the new helpers (mirrors existing exports).
- `job_finder/agent.py` — add `screen_node`, rewire edges, read `TARGET_LOCALE`.
- `job_finder/requirements.txt` — add `httpx`.
- `.env` — add `TARGET_LOCALE` (not committed; git-ignored).

---

### Task 1: `is_dead(status_code: int) -> bool`

**Files:** `tools/main.py` (add), `tools/test_is_dead.py` (create), `tools/__init__.py` (export).

**Interfaces:**
- Produces: `is_dead(status_code: int) -> bool`.
- Contract: `True` for `404`, `410`, any `>= 500`, and the `0` sentinel (glue's network-error
  marker). Everything else (2xx/3xx, and other 4xx like 403) is **not** dead.

**Test cases** (you write the parametrized test):

| status_code | expected | why |
| --- | --- | --- |
| `200` | `False` | live |
| `404` | `True` | gone |
| `410` | `True` | gone |
| `500` | `True` | boundary — first "dead" 5xx |
| `503` | `True` | 5xx |
| `0` | `True` | network-error sentinel |
| `403` | `False` | 4xx but not our dead set (job may exist, just gated) |

- [ ] **Step 1 (Red):** Predict the outcome, then write `test_is_dead.py` with the table above.
- [ ] **Step 2:** Stub `is_dead` in `main.py` returning a deliberately wrong constant; run
      `.venv/bin/python -m pytest job_finder/tools/test_is_dead.py -v` — see it FAIL.
- [ ] **Step 3 (Green):** Write the minimal implementation.
- [ ] **Step 4:** Run the test — all PASS.
- [ ] **Step 5:** Export `is_dead` from `tools/__init__.py`; run the full suite.
- [ ] **Step 6 (Commit):** `git add` the two files + `__init__.py`; commit.

---

### Task 2: `location_matches(location: str, target: str) -> bool`

**Files:** `tools/main.py` (add), `tools/test_location_matches.py` (create), `tools/__init__.py` (export).

**Interfaces:**
- Produces: `location_matches(location: str, target: str) -> bool`.
- Contract: case-insensitive — `True` if `target` is a substring of `location`, **or** `location`
  contains a remote synonym (`remote`, `anywhere`, `worldwide`). This is where "remote-OK" lives.

**Test cases:**

| location | target | expected | why |
| --- | --- | --- | --- |
| `"Mexico City, Mexico"` | `"Mexico"` | `True` | country substring |
| `"London, UK"` | `"Mexico"` | `False` | different country |
| `"MEXICO CITY"` | `"mexico"` | `True` | case-insensitive both ways |
| `"Remote"` | `"Mexico"` | `True` | remote synonym, ignores target |
| `"Anywhere"` | `"Mexico"` | `True` | remote synonym |
| `"Remote - Worldwide"` | `"Mexico"` | `True` | remote synonym |
| `""` | `"Mexico"` | `False` | empty location, not remote |

- [ ] **Step 1 (Red):** Predict, then write `test_location_matches.py`.
- [ ] **Step 2:** Stub returning a wrong value; run — see it FAIL.
- [ ] **Step 3 (Green):** Minimal implementation (think: which check comes first, remote or target?).
- [ ] **Step 4:** Run — PASS.
- [ ] **Step 5:** Export from `__init__.py`; run full suite.
- [ ] **Step 6 (Commit).**

---

### Task 3: `extract_job_location(html: str) -> str | None`

**Files:** `tools/main.py` (add), `tools/test_extract_job_location.py` (create), `tools/__init__.py` (export).

**Interfaces:**
- Produces: `extract_job_location(html: str) -> str | None`.
- Contract: find the `<script type="application/ld+json">` block whose JSON is (or contains) a
  `JobPosting`, and return its `jobLocation` address as text. Return `None` if there is no JSON-LD
  block, the JSON is malformed, or there is no `jobLocation`. Pure — `html` is passed in.
- Note: `json` is already imported in `agent.py`; here you'll parse the `<script>` contents. Use a
  guard-clause style (guard → parse → guard → return), like the `extract_*_link` extractors.
- schema.org shape to target: `jobLocation.address.addressLocality` / `addressRegion` /
  `addressCountry` (return a readable joined string or the country — you'll pin the exact shape
  with the fixture in Red).

**Test cases** (capture one real ATS page to a fixture string during Red; craft the rest inline):

| html | expected | why |
| --- | --- | --- |
| JSON-LD `JobPosting` with `jobLocation` = Mexico City | the location text | happy path |
| HTML with **no** `<script type="application/ld+json">` | `None` | no structured data |
| `<script type="application/ld+json">` containing malformed JSON | `None` | must not raise |
| JSON-LD `JobPosting` with **no** `jobLocation` key | `None` | present but locationless |

- [ ] **Step 1 (Red):** Fetch one live post URL (any survivor from a recent run) and save its HTML
      as a fixture constant; predict, then write `test_extract_job_location.py` with the 4 cases.
- [ ] **Step 2:** Stub returning a wrong non-`None` value (so the `None` cases can't pass
      vacuously); run — see it FAIL.
- [ ] **Step 3 (Green):** Minimal implementation; ensure malformed JSON returns `None`, not a raise.
- [ ] **Step 4:** Run — PASS.
- [ ] **Step 5:** Export from `__init__.py`; run full suite.
- [ ] **Step 6 (Commit).**
- [ ] **Refactor note:** if a vendor turns out **not** to emit JSON-LD, that's the deferred
      per-vendor fallback in the spec — flag it, don't solve it inside this rep.

---

### Task 4: `should_keep(status_code: int, html: str, target: str) -> bool`

**Files:** `tools/main.py` (add), `tools/test_should_keep.py` (create), `tools/__init__.py` (export).

**Interfaces:**
- Consumes: `is_dead`, `extract_job_location`, `location_matches` (Tasks 1–3).
- Produces: `should_keep(status_code: int, html: str, target: str) -> bool`.
- Contract (single decision point):
  1. `is_dead(status_code)` → `False`.
  2. else `extract_job_location(html) is None` → `True` (keep unknowns — spec decision).
  3. else → `location_matches(location, target)`.

**Test cases** (drive each branch; keep `html` minimal — a tiny JSON-LD string or empty):

| status_code | html | target | expected | branch |
| --- | --- | --- | --- | --- |
| `404` | (in-locale JSON-LD) | `"Mexico"` | `False` | dead wins over good location |
| `200` | (no JSON-LD) | `"Mexico"` | `True` | live + unknown location → keep |
| `200` | (JSON-LD = Mexico City) | `"Mexico"` | `True` | live + in-locale |
| `200` | (JSON-LD = London) | `"Mexico"` | `False` | live + out-of-locale |
| `200` | (JSON-LD = Remote) | `"Mexico"` | `True` | live + remote |

- [ ] **Step 1 (Red):** Predict, then write `test_should_keep.py`. (This composes real helpers —
      no mocking; reuse the fixture strings from Task 3.)
- [ ] **Step 2:** Stub returning a wrong constant; run — see it FAIL (confirm the dead-wins case
      in particular fails against the stub).
- [ ] **Step 3 (Green):** Minimal implementation composing the three helpers in contract order.
- [ ] **Step 4:** Run — PASS.
- [ ] **Step 5:** Export from `__init__.py`; run full suite (expect the prior count + all new cases).
- [ ] **Step 6 (Commit).**

---

### Task 5: Wire `screen_node` (glue — verified via `adk web`, not unit-tested)

**Files:** `agent.py` (add node + rewire edges + read config), `requirements.txt` (add `httpx`),
`.env` (add `TARGET_LOCALE`).

**Interfaces:**
- Consumes: `should_keep` (Task 4); the deduped `list[dict]` from `collect_posts`.
- Produces: an `Event(output=survivors)` consumed unchanged by `export_node`.

**Contract / behavior:**
- Read `TARGET_LOCALE = os.getenv("TARGET_LOCALE")`. If missing, `yield Event(output={"error":
  "missing configuration"})` — a visible error Event, **not** `return`/`None` (silent dead-end per
  the ADK gotchas), matching `export_node`'s existing guard style.
- Async: with an `httpx.AsyncClient` and a bounded `asyncio.Semaphore(10)`, fetch every post `url`
  concurrently. Each fetch returns `(status_code, text)`; wrap in try/except mapping **any**
  exception/timeout to `(0, "")` (→ `is_dead` → drop, per spec §5).
- Keep posts where `should_keep(status_code, text, TARGET_LOCALE)` is `True`;
  `yield Event(output=survivors)`.

**Steps:**

- [ ] **Step 1:** `echo 'TARGET_LOCALE=Mexico' >> .env` (or your real target). Add `httpx` to
      `requirements.txt`; `.venv/bin/python -m pip install httpx`.
- [ ] **Step 2:** Import `should_keep` in `agent.py`; add `import asyncio`, `import httpx`.
- [ ] **Step 3:** Write `screen_node` per the contract above (you write it; I'll review the
      concurrency + error mapping).
- [ ] **Step 4:** Rewire edges: replace `(collect_posts, export_node)` with
      `(collect_posts, screen_node)` and `(screen_node, export_node)`.
- [ ] **Step 5 (Verify):** `adk web` — run an end-to-end search. Confirm: survivor count `<`
      pre-screen count (dead/out-of-locale dropped), a known-dead URL is gone, and a remote post
      survives. Check the "N posts → M after screen" delta, like the 06-10 dedup measurement.
- [ ] **Step 6 (Commit).**
- [ ] **Changelog:** add a `2026-07-13` entry to `CLAUDE.md` (session goal, decisions, new suite
      count, the pre/post-screen delta).

---

## Self-Review

- **Spec coverage:** disposition=drop (Task 5 filter) ✓; locale=country+remote (Task 2) ✓;
  mechanism=HTTP+structured-data (Task 3 + Task 5 fetch) ✓; unknown-location=keep (Task 4 branch 2) ✓;
  timeout=drop (Task 5 `(0,"")` → `is_dead`) ✓; shared JSON-LD not per-vendor (Task 3) ✓;
  node placement (Task 5 edges) ✓; config `TARGET_LOCALE` + `httpx` dep (Task 5) ✓.
- **Placeholder scan:** test cases given as concrete input→expected tables (tutoring mode: user
  writes the pytest/impl by design, not a placeholder gap). No TBDs.
- **Type consistency:** `should_keep(status_code, html, target)` signature identical in Tasks 4 & 5;
  `extract_job_location -> str | None` consumed correctly by `should_keep` branch 2.
