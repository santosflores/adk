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

## Working style

The user is **learning TDD via step-by-step tutoring** (ongoing, across the week).
When tutoring: coach one step at a time, have the user write the code and run it
themselves, ask them to predict outcomes before running, and reinforce
Red → Green → Refactor. Do **not** implement for them unless asked.

## Changelog — current state

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
- **In flight: `dedupe_posts(posts) -> list[dict]`** — decisions locked, tests not yet written:
  keyed on `id`, **first copy wins** (no reason to prefer later), implemented via `dict` so
  insertion order is preserved (pinned by tests but not promised), **per-board dedup only**
  (same job cross-posted on two ATSes has two ids — out of scope by decision). Test cases agreed:
  empty, no-dups passthrough, same-id-different-snippet keeps first, non-adjacent duplicates.
- **Next after dedupe:** wire the fan-out in `agent.py` — splitter node (domain list),
  `crawl_node` as `parallel_worker=True` taking the domain from `node_input` (replacing the
  hardcoded `site:jobs.ashbyhq.com`) and dispatching to the right extractor, collector node
  calling `dedupe_posts`. Glue verified via `adk web`, per convention.

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
