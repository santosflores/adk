import google.auth
import gspread
import json
import logging
import os

from .models import JobPosition
from .tools import (
    normalize_role,
    is_confident,
    extract_text,
    parse_page,
    extract_ashby_link,
    extract_greenhouse_link,
    extract_lever_link,
    dedupe_posts,
    posts_to_rows,
)
from datetime import datetime
from google.adk import Agent, Context, Workflow, Event
from google.adk.events import EventActions, RequestInput
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams
from google.adk.workflow import node
from google.genai import types
from typing import Any

from dotenv import load_dotenv

load_dotenv()

AGENT_MODEL = "gemini-3.1-flash-lite"
RETRY_CONFIG = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            initial_delay=2, attempts=10, exp_base=3.5
        ),
    )
)
ATS_EXTRACTORS = {
    "jobs.ashbyhq.com": extract_ashby_link,
    "boards.greenhouse.io": extract_greenhouse_link,
    "jobs.lever.co": extract_lever_link,
}
SERP_API_KEY = os.getenv("SERP_API_KEY")

logger = logging.getLogger(__name__)

serp_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=f"https://mcp.serpapi.com/{SERP_API_KEY}/mcp",
        timeout=120,
    ),
)


@node
def normalize_role_node(node_input: Any):
    raw = extract_text(node_input)
    if not raw:
        return Event(
            output=node_input,
            actions=EventActions(route="invalid"),
        )
    return Event(
        output=normalize_role(raw),
        actions=EventActions(route="valid"),
    )


@node
def check_confidence(node_input: Any):
    if is_confident(node_input["confidence"]):
        return Event(
            output=node_input,
            actions=EventActions(
                route="accept",
                state_delta={
                    "job_position": node_input["name"],
                },
            ),
        )
    return Event(
        output=node_input,
        actions=EventActions(route="retry"),
    )


@node
async def request_role(ctx: Context):
    yield RequestInput(
        interrupt_id=f"role_{ctx.attempt_count}",  # unique per iteration
        message="Please provide a valid role name",
        response_schema=str,
    )


@node
def get_ats_domains():
    return list(ATS_EXTRACTORS.keys())


@node
def collect_posts(node_input: list[list[dict]]):
    posts = [p for worker in node_input for p in worker]
    posts = dedupe_posts(posts)
    yield Event(output=posts)


@node
def export_node(ctx: Context, node_input: list[dict]):
    spreadsheet_id = os.getenv("SHEETS_WORKBOOK_KEY")
    if not spreadsheet_id:
        yield Event(output={"error": "missing configuration"})
    else:
        creds, _ = google.auth.default(scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_id)
        values = posts_to_rows(node_input)
        tab = f"{datetime.now():%Y-%m-%d %H-%M} {ctx.state['job_position']}"
        ws = sh.add_worksheet(title=tab, rows=len(values) + 10, cols=len(values[0]))
        ws.update(values)
        yield Event(output={"worksheet": tab, "url": sh.url, "count": len(node_input)})


@node(parallel_worker=True)
async def crawl_node(ctx: Context, node_input: Any):
    search = next(t for t in await serp_tools.get_tools() if t.name == "search")
    posts = []

    serp_params = {
        "q": f"site:{node_input} {ctx.state['job_position']}",
        "engine": "duckduckgo",
        "m": 20,
    }
    while True:
        if len(posts) > 0:
            serp_params["start"] = len(posts) + 1
        result = await search.run_async(
            args={"params": serp_params, "mode": "compact"},
            tool_context=ctx,
        )
        organic_results = json.loads(result["content"][0]["text"])["organic_results"]
        before = len(posts)
        posts.extend(parse_page(organic_results, ATS_EXTRACTORS[node_input]))
        if len(posts) >= 35:
            break
        if len(posts) == before:
            break
    return posts


input_evaluator = Agent(
    name="input_evaluator",
    model=AGENT_MODEL,
    instruction="""You are an evaluator. Your only goal is to evaluate an input and determine 
    if it is a valid job position name. Attach a confidence value.""",
    output_schema=JobPosition,
    generate_content_config=RETRY_CONFIG,
)

root_agent = Workflow(
    name="root_agent",
    edges=[
        (
            "START",
            normalize_role_node,
        ),
        (
            normalize_role_node,
            {
                "valid": input_evaluator,
                "invalid": request_role,
            },
        ),
        (
            input_evaluator,
            check_confidence,
        ),
        (
            check_confidence,
            {
                "accept": get_ats_domains,
                "retry": request_role,
            },
        ),
        (
            request_role,
            normalize_role_node,
        ),
        (get_ats_domains, crawl_node),
        (crawl_node, collect_posts),
        (collect_posts, export_node),
    ],
)
