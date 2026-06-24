# Summary

This agent is in charge of finding job posts related to a specific query. The user can share a position name and the agent will:

0) User shares a position name
1) Search across three different providers: Ashby, Greenhouse, Lever
2) Join the results of the three providers
3) Create evidence inside a DB to track posts

Work Plan:

* Make the agent to loop the conversation until a position is given (Used DynamicWorkflows)
  * Done, the decision made is creating a workflow that implements a while loop, the agent doesn't allow to move into the next step until the input requirement is met
* Fanout 3 agents to search the job board providers
* Use an agent to stitch the results into a single file

## Deployment (Vertex AI Agent Engine)

Deployed to **Agent Engine** (a.k.a. Reasoning Engine / Vertex AI Agent Runtime) via the
ADK CLI's source-based deploy — no Dockerfile. Run everything from the **workspace root**
with the venv interpreter.

### Deploy command

```bash
.venv/bin/adk deploy agent_engine \
  --project fieldhouse-dev-495616 \
  --region us-central1 \
  --display_name job_finder \
  --agent_engine_id 1808958861214744576 \   # reuse the existing engine; omit to create a new one
  job_finder
```

Deploys take ~5–10 min. The command bundles the whole `job_finder/` directory (including
`.env`, so `SERP_API_KEY` ships as an env var — fine for dev, move to Secret Manager for prod).

### One-time prerequisites (local + project)

```bash
# 1. The deploy CLI needs the Vertex SDK locally — it is NOT a runtime dep, it's the
#    tooling that uploads the engine. Without it: "Deploy failed: No module named 'vertexai'".
.venv/bin/pip install "google-cloud-aiplatform[agent_engines,adk]"

# 2. Local creds for the upload (the deployed agent itself runs as the engine's service account).
gcloud auth application-default login

# 3. Enable the APIs the agent uses at runtime.
gcloud services enable aiplatform.googleapis.com sheets.googleapis.com drive.googleapis.com \
  --project=fieldhouse-dev-495616
```

### Gotchas (each cost a failed deploy — debug via Cloud Logging, see below)

1. **`global` is not a valid Agent Engine region.** `.env` has `GOOGLE_CLOUD_LOCATION=global`
   (valid for the Gemini model endpoint), but the engine resource needs a real region. Always
   pass `--region us-central1`; the bare command picks up `global` from `.env` and fails.

2. **`adk deploy` auto-generates a `requirements.txt` containing only `google-adk`** when the
   agent dir has none — and it **ignores the workspace-root `requirements.txt`**. The agent's
   own deps must live in **`job_finder/requirements.txt`** (this file is what the cloud build
   installs). The root `requirements.txt` only affects your local venv.

3. **ADK's server needs the `[a2a]` extra or it won't boot.** On startup the ADK FastAPI app
   builds an A2A task store (`from a2a.server.tasks import InMemoryTaskStore`). Plain
   `google-adk` doesn't pull `a2a-sdk` → `ModuleNotFoundError: No module named 'a2a'`, engine
   "failed to start and cannot serve traffic." This is ADK infra, not our code.

4. **The SerpAPI tool needs the `[mcp]` extra.** `McpToolset` / `StreamableHTTPConnectionParams`
   require the `mcp` package → `No module named 'mcp'` at agent import.

   → Both extras combined in `job_finder/requirements.txt`: `google-adk[a2a, mcp]==2.2.0`.
   **Rule of thumb:** any ADK feature backed by an optional extra must be named here, because the
   cloud build only installs what's pinned. The local venv already had them, so these only ever
   surface at deploy time.

5. **`__init__.py` is required for the bundle.** `agent.py` uses package-relative imports
   (`from .models`, `from .tools`). `adk web` tolerates a missing `__init__.py`; the deployed
   bundle does not. `job_finder/__init__.py` must contain `from . import agent`.

6. **No service-account key file in the cloud.** The Sheets export originally read `sa.json` via
   `gspread.service_account(filename=...)`. That key file can't ship to Agent Engine (and `sa.json`
   is git-ignored). `export_node` now authenticates with **Application Default Credentials** —
   `google.auth.default(scopes=[spreadsheets, drive])` + `gspread.authorize(creds)` — so it runs as
   the engine's runtime service account. `sa.json` and the `GOOGLE_SA_KEY_PATH` references were
   removed. **You must share the target spreadsheet (Editor) with the runtime SA:**

   (i.e. `service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com`). If export 403s,
   it's almost always this share or a disabled Sheets/Drive API.

## Debugging a failed/started engine

Startup crashes show up as a Python traceback in the engine's logs. Pull them with:

```bash
gcloud logging read \
  'resource.type="aiplatform.googleapis.com/ReasoningEngine" AND resource.labels.reasoning_engine_id="1808958861214744576" AND severity>=ERROR' \
  --project=fieldhouse-dev-495616 --limit=10 --freshness=15m \
  --format='value(timestamp,textPayload)'
```

Use a tight `--freshness` window so you don't read stale logs from a previous failed boot.
Reuse `--agent_engine_id` on redeploy to update the same engine in place instead of orphaning
failed ones.
