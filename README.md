# ADK Agents Workspace

A collection of [Google ADK](https://google.github.io/adk-docs/) agent projects.
Each top-level directory is a **self-contained agent package** that can be run on its
own with the `adk` CLI.

## Repository structure

```sh
adk/
├── requirements.txt        # shared Python dependencies
├── .venv/                  # virtual environment (git-ignored)
│
├── agent_team/             # ← reference implementation (fully built out)
│   ├── __init__.py         #   exposes the package: `from . import agent`
│   ├── agent.py            #   defines `root_agent` (+ any sub-agents)
│   ├── main.py             #   optional standalone scripted runner
│   ├── tools/              #   tool + callback implementations
│   └── .env                #   per-agent Google Cloud / Vertex AI config
│
├── blueprint_agent/        # additional agent packages, same layout
├── multitool_agent/
├── my_agent/
├── researcher/
├── sequential_agent/
└── test_agent/
```

### Agent package convention

Every agent directory follows the same shape:

| File           | Purpose                                                         |
| -------------- | --------------------------------------------------------------- |
| `__init__.py`  | Marks the package and re-exports `agent` (`from . import agent`)|
| `agent.py`     | Defines `root_agent` — the entry point ADK discovers            |
| `tools/`       | (optional) Tool functions and lifecycle callbacks               |
| `main.py`      | (optional) Standalone script that runs a conversation directly  |
| `.env`         | Per-agent Google Cloud / Vertex AI configuration                |

**Imports are package-relative** (e.g. `from .tools import ...`). This means agent
code must be loaded as part of its package — always run commands from the
**workspace root** (this directory), never from inside an agent folder.

> `agent_team` is the most complete example. Use it as the template when fleshing
> out the other agent packages.

## Setup

1. Install dependencies (from the workspace root):

   ```bash
   uv pip install -r requirements.txt
   ```

2. Configure the `.env` inside the agent you want to run:

   VERTEX

   ```dotenv
   GOOGLE_GENAI_USE_VERTEXAI=TRUE
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_LOCATION=global
   ```

   API DEV
  
   ```dotenv
   GOOGLE_API_KEY=GEMINI_API_KEY
   ```

## Running agents

All commands are run from the **workspace root**.

### Web UI — browse every agent

Starts the ADK developer web interface and discovers **all** agent packages in this
directory. Pick the agent you want from the dropdown:

```bash
adk web
```

### Terminal chat — one specific agent

```bash
adk run <agent_dir>      # e.g. adk run agent_team
```

### Standalone script runner

For agents that ship a `main.py` (currently `agent_team`), run it as a **module** so
the package-relative imports resolve:

```bash
uv run python -m <agent_dir>.main      # e.g. uv run python -m agent_team.main
```

> ⚠️ `python <agent_dir>/main.py` will **not** work — running the file as a loose
> script breaks the package-relative imports. Always use the `-m <agent_dir>.main`
> form from the workspace root.

### REST API server — call agents over HTTP

Starts a FastAPI server exposing every agent over REST (defaults to
`http://127.0.0.1:8000`):

```bash
adk api_server                 # add --port 8080 to change the port
```

The **`app_name` in requests is the agent directory name** (e.g. `agent_team`).

**1. Create a session** (required before the first run; `state` is optional):

```bash
curl -s -X POST http://127.0.0.1:8000/apps/agent_team/users/u_123/sessions/s_123 \
  -H "Content-Type: application/json" \
  -d '{"state": {"user_preference_temperature_unit": "Celsius"}}'
```

**2. Run the agent** — returns a JSON array of all events; the final reply is the
`text` in the last event's `content.parts`:

```bash
curl -s -X POST http://127.0.0.1:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "agent_team",
    "user_id": "u_123",
    "session_id": "s_123",
    "new_message": {"role": "user", "parts": [{"text": "What is the weather in New York?"}]}
  }'
```

**Stream responses (SSE)** — same body against `/run_sse`; add `"streaming": true`
for token-level streaming:

```bash
curl -N -X POST http://127.0.0.1:8000/run_sse \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "agent_team",
    "user_id": "u_123",
    "session_id": "s_123",
    "new_message": {"role": "user", "parts": [{"text": "Hello there! My name is Santos"}]},
    "streaming": true
  }'
```

Useful inspection endpoints:

```bash
curl -s http://127.0.0.1:8000/list-apps                                    # agents served
curl -s http://127.0.0.1:8000/apps/agent_team/users/u_123/sessions/s_123   # inspect a session
```

`/run` and `/run_sse` request body fields:

| Field         | Required | Notes                                                          |
| ------------- | -------- | -------------------------------------------------------------- |
| `app_name`    | yes      | Agent directory name (e.g. `agent_team`)                       |
| `user_id`     | yes      | Any string                                                     |
| `session_id`  | yes      | Must already exist (create it first, step 1)                   |
| `new_message` | yes      | `{"role": "user", "parts": [{"text": "..."}]}`                 |
| `streaming`   | no       | `true` for token-level streaming (use with `/run_sse`)         |
| `state_delta` | no       | Dict merged into session state for this turn                   |

## Quick reference

| Goal                          | Command (from workspace root)         |
| ----------------------------- | ------------------------------------- |
| Browse all agents in Web UI   | `adk web`                             |
| Chat with one agent (CLI)     | `adk run <agent_dir>`                 |
| Serve agents over REST        | `adk api_server`                      |
| Run an agent's script runner  | `uv run python -m <agent_dir>.main`   |
| Install dependencies          | `uv pip install -r requirements.txt`  |
