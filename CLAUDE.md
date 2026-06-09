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
- **Pure logic lives in `<agent>/tools/main.py`** — small, framework-free functions (`normalize_role`, `is_confident`, `extract_text`). Tested in `<agent>/tools/test_*.py`.
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

### 2026-06-08

- **`job_finder/`** is the active TDD project. Structure:
  - `tools/main.py` — pure, tested: `normalize_role(raw)`, `is_confident(confidence)`, `extract_text(node_input)`, `CONFIDENCE_THRESHOLD = 0.95`.
  - `tools/test_*.py` — 15 passing tests (`test_normalize_role`, `test_is_confident`, `test_extract_text`).
  - `agent.py` — ADK 2.0 `Workflow` (`root_agent`). Nodes: `normalize_role_node` (routes `valid`/`invalid`), `check_confidence` (routes `accept`/`retry`), `request_role` (HITL re-prompt), `finish`. LLM node: `input_evaluator` (output_schema `JobPosition`).
- **Done so far:** TDD'd `normalize_role`, `is_confident`, `extract_text`; isolated pure logic from the ADK stack for fast/warning-free tests; wired `normalize_role_node` as a thin adapter (no duplicate logic); added deterministic empty-input routing → `request_role` (no wasted LLM call).
- **Known/open (cosmetic):** `check_confidence`'s `__DEFAULT__: input_evaluator` route is unreachable/odd — left intentionally. No workflow-level integration test yet (glue verified via `adk web`).
- **Next candidate reps:** an end-to-end integration test for the workflow; threshold dependency-injection (`is_confident(confidence, threshold=...)`).
