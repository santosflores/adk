"""Minimal public wrapper for the job_finder agent.

One FastAPI service that (a) serves a small web page and (b) proxies the browser's
request to the Vertex AI Agent Engine ``streamQuery`` endpoint, streaming the SSE
response straight back. The browser never sees a GCP token — this service holds
the credential (ADC: your user creds locally, the attached service account on
Cloud Run) and mints a short-lived token per request.

No auth / rate limiting yet — accessibility-first MVP. Add those before real
public traffic (each run costs Gemini + SerpApi + 100+ fetches).

Run locally:  uvicorn main:app --reload --port 8080   (uses your `gcloud` ADC)
Deploy:       gcloud run deploy job-finder-web --source . --region us-central1 --allow-unauthenticated
"""

import os

import google.auth
import google.auth.transport.requests
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse

ENGINE_URL = os.getenv(
    "ENGINE_URL",
    "https://us-central1-aiplatform.googleapis.com/v1/projects/fieldhouse-dev-495616"
    "/locations/us-central1/reasoningEngines/365555180642500608:streamQuery?alt=sse",
)
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_creds, _ = google.auth.default(scopes=SCOPES)
_STATIC = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI()


def _access_token() -> str:
    """Mint/refresh a short-lived GCP access token from ADC."""
    _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


@app.get("/")
def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


@app.post("/run")
async def run(req: Request):
    payload = await req.json()
    role = (payload.get("role") or "").strip()
    body = {
        "class_method": "stream_query",
        "input": {"user_id": "web", "message": role},
    }

    async def stream():
        headers = {
            "Authorization": f"Bearer {_access_token()}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", ENGINE_URL, headers=headers, json=body
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")
