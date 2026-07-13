# CLAUDE.md

Guidance for Claude Code when working in this repo. For run/setup commands and the
agent-package convention, see [README.md](README.md) — this file does not repeat them.

## What this repo is

A workspace of self-contained [Google ADK](https://google.github.io/adk-docs/) agent
packages (one per top-level directory). The active focus is **`job_finder/`**, which is
being used as a hands-on **TDD tutoring** project (see the changelog and the
"Working style" section below).

## Stack

| Thing | Version / value |
| --- | --- |
| Language | Python **3.14.4** (in `.venv/`) |
| Agent framework | **google-adk 2.2.0** — uses the experimental **ADK 2.0 Workflow API** (`google.adk.workflow`: nodes, edges, routing, HITL) |
| LLM SDK | google-genai 2.8.0 |
| Models | Gemini (`gemini-3.1-flash-lite` in job_finder) |
| Schemas | pydantic 2.13.4 |
| Tests | **pytest 9.0.3** (⚠️ NOT in `requirements.txt` — installed into the venv manually) |

> Always run Python via the venv interpreter so you get 3.14, not a pyenv global:
> use `.venv/bin/python -m <cmd>` (or `python -m <cmd>` with the venv activated).
> A bare `pytest` may resolve to the wrong interpreter.

## Testing conventions (established during TDD work)

- **Run tests:** `.venv/bin/python -m pytest job_finder/tools/ -v` (run from workspace root; imports are package-relative).
- **Pure logic lives in `<agent>/tools/main.py`** — small, framework-free functions (`normalize_role`, `is_confident`, `extract_text`, `parse_page` + per-ATS `extract_*_link` extractors). Tested in `<agent>/tools/test_*.py`.
- **Per-ATS URL extractors follow the guard-clause house style** (guard → assign → guard → return) and are deliberately duplicated per vendor — shared URL shapes are coincidence, not contract.
- **Keep `google.adk` / `google.genai` out of pure modules.** Importing them at module top drags the whole stack into the test run → slow + `DeprecationWarning`s. Two techniques used here: **lazy import** inside the function, or **duck typing** (`getattr(x, "parts", ...)`) to avoid the import entirely. Fast tier runs ~0.02s warning-free; only tests that build a real `types.Content` pay the cost.
- **Nodes/agents are thin adapters** over the tested pure functions — they hold control flow (routing, Events), not logic. Verify the glue layer with `adk web`, not unit tests.
- **Test count tracks branches, not type richness** — write one case per decision *your* code makes; don't test the framework's types.
- Parametrize same-assertion-many-inputs cases; cover boundaries explicitly (e.g. `is_confident` tests `0.94`/`0.95`).

## ADK gotchas learned here

- **`START` hands a node a plain `str`, not `types.Content`** in google-adk 2.2.0 (contradicts the 2.0 cheatsheet). A node after `START` or a HITL resume should handle both — guard by `isinstance` before touching `.parts`.
- Edge tuples are **chains**: `("START", a, b, c)` means `START → a → b → c`. Split a chain into separate edges when a middle node needs to route conditionally.
- A node returning `None` emits **no event** → downstream never fires (silent dead-end). Return `""` or an `Event(route=...)` instead if you want flow to continue.
- Routing nodes want a `__DEFAULT__` edge or ADK shows `[NO DEFAULT]`.
- **"cancelling N leftover tasks" after a ParallelWorker run is cosmetic** (N == worker count).
  `DynamicNodeScheduler` never prunes completed runs from its registry, so workflow cleanup
  counts every finished worker task as "leftover"; the actual `cancel()` is guarded by
  `task.done()` and no-ops. Verified against `_dynamic_node_scheduler.py` /`_workflow.py:848`
  in google-adk 2.2.0. Don't silence the logger — the same line fires for *real* stuck tasks.
  **Upstream status (checked 2026-06-10):** code on google/adk-python `main` is identical
  (`get_dynamic_tasks()` has no `task.done()` filter; `_record_result` never prunes), and no
  issue/PR reports it ("leftover tasks", "ParallelWorker" searches come up empty). Not yet
  filed — the drafted report lives in `notes/adk-issue-leftover-tasks.md`.

## Working style

The user is **learning TDD via step-by-step tutoring** (ongoing, across the week).
When tutoring: coach one step at a time, have the user write the code and run it
themselves, ask them to predict outcomes before running, and reinforce
Red → Green → Refactor. Do **not** implement for them unless asked.

## Changelog — current state

### 2026-07-13

- **Session goal: screen collected links — follow each, read it, drop dead + wrong-locale
  posts** before export (complete). New `screen_node` between `collect_posts` and
  `export_node`. Suite now **66 passing** (25 new cases across 6 test files).
- **Mechanism pivot mid-build (the session's big lesson): JSON-LD → ATS JSON APIs.** Design
  started on "HTTP GET each page + parse a shared schema.org `JobPosting` JSON-LD." Before
  writing the parser we **probed one live page per ATS** (empirical, like the 06-10 dedup
  measurement) and the shared-contract assumption collapsed: **Greenhouse emits no JSON-LD** on
  its hosted board, Lever's `jobLocationType` is null and `addressCountry` is null (only
  `"Palo Alto, CA"`). Probing the **public ATS JSON APIs** instead — reachable from the `id` we
  already extract + the company slug (`parts[3]` of every ATS URL) — gave clean structured data:
  Lever `country`+`workplaceType`, Ashby `addressCountry`+`isRemote`, Greenhouse `offices`. So we
  revived the brainstorming-rejected "Approach C." Recorded as an amendment in the spec.
- **Pure layer (TDD'd, fast tier, `tools/main.py`), build order:**
  - `is_dead(status_code)` — dead = `{404,410,0-sentinel}` ∪ `>=500`. **Allowlist lesson:**
    first impl was `code >= 404` (passed the 5 cases but marked `429`/`403` dead → would drop live
    jobs); a `(429, False)` Red forced the exact-set-plus-range shape. Enumerate the small stable
    set; default unknowns to the safe direction.
  - `location_matches(country, target)` — case-insensitive substring; remote-synonym branch
    **removed** (remote became a structured bool, not a text scrape).
  - Per-vendor `extract_{lever,ashby,greenhouse}_fields(job) -> (country, is_remote)` — house-style
    duplication (like `extract_*_link`). **Real-data catches:** Lever's on-site value is `"onsite"`
    (no hyphen) — a *guessed* `"on-site"` fixture made a broken `!= "on-site"` denylist pass green
    (allowlist `workplaceType in ("remote","hybrid")` fixed it — "hybrid is fine" = keep). Ashby
    `isRemote` is **tri-state** (True/False/**None**, None common) → only explicit `True` counts.
    Greenhouse has no structured country/remote → `is_remote` is a text scan of `location.name`,
    `country` prefers structured `offices[].location` with `location.name` fallback.
  - `should_keep(status_code, country, is_remote, target)` — the one decision point; guard order
    **dead → remote → unknown-country(keep) → location_matches**. Dead beats a remote in-locale job.
- **Glue (`tools/screen.py`, not unit-tested per house rule):** async `httpx` per-vendor fetch,
  bounded `Semaphore(10)`. Lever/Greenhouse are single-job-by-id (404 = dead); **Ashby is
  board-level** — pre-fetch each company's board once, `id`-absent = dead. Deliberately kept out of
  `agent.py`/`google.adk` so it's headlessly runnable. `screen_node` in `agent.py` is a thin
  adapter (reads `TARGET_LOCALE`, missing → error Event, not a silent dead-end).
- **Verification instead of `adk web`:** `job_finder/verify_screen.py` exercises the real
  fetch+parse+decide path against live APIs with a live + deliberately-dead post per ATS —
  **7 posts → 3 survivors**, every live/dead/wrong-locale path correct. (Full workflow through
  `adk web` still worth a run for the SerpAPI+LLM front half.)
- **Config/deps:** `TARGET_LOCALE` in `.env` (git-ignored); `httpx==0.28.1` pinned in
  `requirements.txt`. Spec + amendment at
  `docs/superpowers/specs/2026-07-12-link-screening-design.md`; plan at
  `docs/superpowers/plans/2026-07-13-link-screening.md`.
- **Open / deferred:** cross-vendor **country normalization** (`"US"` vs `"United States"` vs
  Greenhouse free text / ISO `"IE"`) — a `TARGET_LOCALE` must currently match the vendor's spelling;
  fix is an alias map or multi-form target. The Lever `extract_lever_link` clean-before-check
  reorder (open since 06-10) is still open.

### 2026-06-22

- **Session goal: export results to a Google Sheets workbook** (complete). Built via the
  established pure/glue split.
- **TDD'd `posts_to_rows(posts) -> list[list]`** in `tools/main.py` (suite now **38 passing**,
  4 new cases in `tools/test_posts_to_rows.py`): turns the deduped `collect_posts` dicts
  (`{title, url, snippet, id}`) into the `list[list]` shape `gspread.Worksheet.update()` wants
  — header row + one row per post. Decisions baked into tests: `EXPORT_COLUMNS` is the **single
  source of truth** for column order *and* header labels (each row built by walking it, so
  reordering the constant reorders the data automatically); empty list → **header-only** (a tab
  with columns, no rows); missing key → **per-cell blank** via `p.get(e, "")` (row survives, one
  field empty — degrades per-cell, not per-row). **No `google.*` imports** → stays in the fast
  tier. Chose `list[list]` over CSV strings deliberately: gspread escapes cells itself, so a
  comma inside a snippet stays in one column.
- **Wired `export_node`** (glue, in `agent.py`, verified in `adk web` — not unit-tested per house
  rule). After `collect_posts`: resolves the SA key path against `__file__` (the `.env` value
  `GOOGLE_SA_KEY_PATH=sa.json` is relative; `adk web` runs from workspace root, so a bare
  relative path wouldn't resolve), authorizes gspread, opens the workbook by key
  (`SHEETS_WORKBOOK_KEY`), creates a **new tab per run** named `{YYYY-MM-DD HH-MM} {job_position}`
  (colon-free — avoids same-day collisions and any sheet-title validation issues), writes
  `posts_to_rows(...)`, and yields a result Event. New edge: `(collect_posts, export_node)`.
  Both config-missing guards `yield` a visible **error Event** (not `return`/`None` — that's a
  silent dead-end in a generator node, per the ADK gotchas).
- **Auth pivot:** original plan was service-account + key, but the org enforced
  `iam.disableServiceAccountKeyCreation`. User is the org owner → overrode the constraint at the
  **project** level (not org-wide) to keep the guardrail elsewhere. Key is `job_finder/sa.json`,
  **git-ignored** along with `.env` (root `.gitignore`).
- **Deps:** added `gspread==6.2.1` (+ `google-auth-oauthlib`, `oauthlib`, `requests-oauthlib`) to
  `requirements.txt` — real runtime deps (unlike pytest, dev-only).
- **First live run:** results landed in a new worksheet tab. Spec at
  `docs/superpowers/specs/2026-06-19-google-sheets-export-design.md`.
- **Next candidate reps:** coerce non-str cells in `posts_to_rows` (UUID `id`) when a test demands
  it; the orphaned `formatter_agent` is now fully bypassed (`export_node` is terminal) — remove or
  repurpose it; the Lever clean-before-check reorder (still open from 06-10); end-to-end workflow
  integration test.

### 2026-06-10

- **Session goal: fan out `crawl_node` into 3 parallel crawlers** — same `job_position`, one per
  ATS domain (Ashby, Greenhouse, Lever). **Design chosen:** ADK `ParallelWorker`
  (`@node(parallel_worker=True)`) over the JoinNode diamond — a splitter node emits the domain
  list, ADK runs one worker per item (each gets one domain as `node_input`, `job_position` from
  shared `ctx.state`), the next node receives a list of the 3 results (the aggregation point,
  where dedup lives). Not wired yet — pure layer first.
- **Refactored `parse_page`** (refactor-first, stayed green at 20 with zero new tests): the
  Ashby-specific URL logic moved into `extract_ashby_link(link) -> tuple[id, url] | None`
  (`None` = skip entry), and `parse_page` takes a **required**
  `extract_link: Callable[[str], tuple[str, str] | None]` parameter. Call sites (tests +
  `crawl_node`) pass the extractor explicitly.
- **TDD'd `extract_greenhouse_link`**: shape `boards.greenhouse.io/{company}/jobs/{numeric_id}`
  — id at `parts[5]`, validated with `.isdigit()` *after* stripping the query string; URL rebuilt
  from `parts[:5]` + clean id (query strings stripped from both id and url). Took 5 versions
  (`int()` crash on `""`/query strings → branch-and-mutate → possibly-unbound bug → `else: return
  None` → sequenced guards). **House style for extractors: guard → assign → guard → return** —
  happy path flat on the left margin, each guard establishes the assumption the next line needs.
- **TDD'd `extract_lever_link`**: shape `jobs.lever.co/{company}/{uuid}` — same shape as Ashby
  **by coincidence, not contract**; deliberately **duplicated** rather than aliased/shared
  (different vendors, either can change its URL scheme independently).
- **Known/open:** `extract_lever_link` validates *before* cleaning (opposite order from
  Greenhouse), so `.../netflix/?lever-origin=x` would yield a post with `id == ""`. Flagged,
  consciously deferred — fix is a one-case Red + reorder to clean-then-check.
- **Suite: 30 passing** (5 Greenhouse + 5 Lever parse cases added, via `parse_page` with the
  respective extractor in `tools/test_parse_page.py`).
- **TDD practices established this session:** every test must be seen to fail once (stub with a
  deliberately *wrong* value — e.g. `("", "")` not `None` — so skip-path cases can't pass
  vacuously); pytest marks exceptions inside the code under test as `FAILED` (with traceback),
  reserving `ERROR` for fixture/setup breakage; the type checker caught two runtime crashes
  pre-test ("None is not iterable" on unguarded unpack, "possibly unbound" after a refactor).
- **TDD'd `dedupe_posts(posts) -> list[dict]`** (suite now **34 passing**): keyed on `id`,
  **first copy wins** (no reason to prefer later), `dict` + insert-if-absent so insertion order
  is preserved (pinned by tests but not promised), **per-board dedup only** (same job
  cross-posted on two ATSes has two ids — out of scope by decision). Four cases in
  `tools/test_dedupe_posts.py`: empty, no-dups passthrough, adjacent dup keeps first snippet,
  non-adjacent dup (guards against neighbors-only implementations).
- **Fan-out wired and verified** (session goal complete). In `agent.py`:
  - `ATS_EXTRACTORS` dispatch table (domain → extractor) lives in **`agent.py`, not tools/** —
    conscious call: it's wiring, and wiring lives with the graph (cost: not unit-testable from
    `tools/`, which is fine for a 3-entry dict).
  - `get_ats_domains` splitter returns `list(ATS_EXTRACTORS.keys())` — map drives the splitter,
    so adding an ATS = one dict entry, no other edits.
  - `crawl_node` is `@node(parallel_worker=True)`: domain arrives as `node_input` (one worker
    per domain), `job_position` from shared state, query is `site:{node_input} ...`, extractor
    via `ATS_EXTRACTORS[node_input]`. SerpAPI `mode="compact"` is deliberate (completes reliably).
  - `collect_posts` collector closes the diamond: flattens the workers' list-of-lists, calls
    `dedupe_posts`, emits the result. Edges: `check_confidence --accept--> get_ats_domains →
    crawl_node → collect_posts`.
  - **Verified in `adk web` 2026-06-10:** all 3 workers (`crawl_node@0/1/2`) delivered;
    **133 posts flattened → 116 after dedup** — first real measurement of the pagination-overlap
    duplication theorized on 06-09 (~13% dups). The "cancelling 3 leftover tasks" warning at
    workflow end was investigated and confirmed cosmetic — see the ADK gotchas section.
- **Next candidate reps:** wire `formatter_agent` after `collect_posts` (it's been orphaned in
  `agent.py` since before today and the collector now produces its natural input); end-to-end
  workflow integration test; the Lever clean-before-check reorder (open item above); threshold
  dependency-injection (`is_confident(confidence, threshold=...)`).

### 2026-06-09

- **TDD'd `parse_page(node_input: list[dict]) -> list[dict]`** in `tools/main.py`: takes SerpAPI
  `organic_results` entries, returns `{title, url, snippet, id}` dicts. Suite is now **20 passing
  tests** (5 new parametrized cases in `tools/test_parse_page.py`). Decisions baked into tests:
  - `id` extracted from the Ashby URL path (`parts[4]`), kept as `str` — pydantic coerces to
    `UUID` when the caller builds `JobPost`.
  - `url` normalized to `.../{company}/{uuid}` — `/application` suffix and query strings dropped.
  - Entries without a UUID segment (company landing pages, e.g. `.../Abridge`,
    `.../PAR%20Technology/`) are **skipped**; one guard covers both failure modes (IndexError on
    short path, empty string on trailing slash).
  - Query-string variant (`...?source=LinkedIn`) covered by a **pinning test** — passes by
    construction, locks the contract against future URL-handling refactors.
- **Design decisions made:** envelope-digging (`result['content'][0]['text']` + `json.loads`)
  stays in `crawl_node` as adapter glue; `date_added` is stamped by the caller, not `parse_page`
  (keeps it pure/deterministic); **dedup belongs at the aggregation level** (the crawl loop
  re-fetches the same search, so duplicates cross page boundaries), not in `parse_page`.
- **Next candidate reps:** pure `dedupe_posts(posts)` keyed on `id`; wire `parse_page` into
  `crawl_node` (replace the raw `posts.append(result)` accumulation); end-to-end workflow
  integration test; threshold dependency-injection (`is_confident(confidence, threshold=...)`).

### 2026-06-08

- **`job_finder/`** is the active TDD project. Structure:
  - `tools/main.py` — pure, tested: `normalize_role(raw)`, `is_confident(confidence)`, `extract_text(node_input)`, `CONFIDENCE_THRESHOLD = 0.95`.
  - `tools/test_*.py` — 15 passing tests (`test_normalize_role`, `test_is_confident`, `test_extract_text`).
  - `agent.py` — ADK 2.0 `Workflow` (`root_agent`). Nodes: `normalize_role_node` (routes `valid`/`invalid`), `check_confidence` (routes `accept`/`retry`), `request_role` (HITL re-prompt), `finish`. LLM node: `input_evaluator` (output_schema `JobPosition`).
- **Done so far:** TDD'd `normalize_role`, `is_confident`, `extract_text`; isolated pure logic from the ADK stack for fast/warning-free tests; wired `normalize_role_node` as a thin adapter (no duplicate logic); added deterministic empty-input routing → `request_role` (no wasted LLM call).
- **Known/open (cosmetic):** `check_confidence`'s `__DEFAULT__: input_evaluator` route is unreachable/odd — left intentionally. No workflow-level integration test yet (glue verified via `adk web`).
- **Next candidate reps:** an end-to-end integration test for the workflow; threshold dependency-injection (`is_confident(confidence, threshold=...)`).
