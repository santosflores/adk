# Google Sheets export — design

**Date:** 2026-06-19
**Status:** approved, pre-implementation

## Goal

Export the deduped job-post results to a Google Sheets workbook at the end of the
`job_finder` workflow.

## Decisions

- **Auth:** service account + `gspread` (headless; no browser). `google-auth` already
  installed; add `gspread`. Service-account JSON path and target workbook key come from
  `.env`. The target workbook is shared with the service account's email (one-time setup).
- **Wiring:** a real ADK node (`export_node`) inside the workflow, after `collect_posts`.
  The Drive MCP (Claude-side only) is *not* usable from `agent.py`, so the node uses
  gspread directly.
- **Worksheet strategy:** one fixed workbook; each run writes a **new tab** named by
  date + job_position. Runs never clobber each other; history is kept.
- **Coding mode:** TDD tutoring — the user writes the code, Red → Green → Refactor.

## Components

### Pure (TDD'd) — `posts_to_rows(posts) -> list[list]` in `tools/main.py`
Turns the `list[dict]` from `collect_posts` (`{title, url, snippet, id}`) into a header
row + one row per post — the `list[list]` shape `gspread.Worksheet.update()` accepts.
No `google.*` / `gspread` imports (keeps the pure tier fast & warning-free).

Test decisions to establish during the rep: column order, header labels, empty-list
behavior (header-only vs empty), missing-key handling.

### Glue (verified in `adk web`) — `export_node` in `agent.py`
`@node` after `collect_posts`. Authorizes gspread from the service-account JSON, opens
the workbook by key, creates a new worksheet named `{date} {job_position}`, and writes
`posts_to_rows(posts)`. Wiring lives with the graph (like `ATS_EXTRACTORS`); not
unit-tested. New edge: `(collect_posts, export_node)`.

## Out of scope

- Cell formatting / styling.
- Appending to or reconciling against prior tabs.
- The orphaned `formatter_agent` (separate cleanup).

## One-time user setup (deferred to wiring step)

Create service-account key in Google Cloud → enable Sheets + Drive APIs → share the
target workbook with the service account's email → put key path + workbook key in `.env`.
