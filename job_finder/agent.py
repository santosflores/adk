import logging

from .models import JobPosition, JobPostList
from .tools import normalize_role, is_confident, extract_text, parse_page

from google.adk import Agent, Context, Workflow, Event
from google.adk.events import EventActions, RequestInput
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams
from google.adk.workflow import node
from google.genai import types
from typing import Any, List

AGENT_MODEL = "gemini-3.1-flash-lite"
RETRY_CONFIG = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            initial_delay=2, attempts=10, exp_base=3.5
        ),
    )
)

logger = logging.getLogger(__name__)
serp_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp.serpapi.com/9fe5b2435864e377177514a474d1390dbc9dc6ed7ae9d9cfb72e97ffa80eff80/mcp",
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
async def request_role(ctx: Context, node_input: Any):
    yield RequestInput(
        interrupt_id=f"role_{ctx.attempt_count}",  # unique per iteration
        message="Please provide a valid role name",
        response_schema=str,
    )


@node
def finish(node_input: dict):
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part(text=f"Captured role: {node_input['name']}")],
        )
    )
    yield Event(output=node_input)


@node
async def crawl_node(ctx: Context, node_input: Any):
    logger.info(f"node_input: {node_input}")
    search = next(t for t in await serp_tools.get_tools() if t.name == "search")

    posts = []
    serp_params = {
        "q": f"site:jobs.ashbyhq.com {ctx.state['job_position']}",
        "engine": "duckduckgo",
    }
    while len(posts) < 35:
        result = await search.run_async(
            args={"params": serp_params, "mode": "compact"},   # <- nested under "params"
            tool_context=ctx,
        )
        
        logger.info(result)
        posts.append(result)
        

    # yield Event(output=JobPostList(posts=posts[:35]))
    


input_evaluator = Agent(
    name="input_evaluator",
    model=AGENT_MODEL,
    instruction="""You are an evaluator. Your only goal is to evaluate an input and determine 
    if it is a valid job position name. Attach a confidence value.""",
    output_schema=JobPosition,
    generate_content_config=RETRY_CONFIG,
)


formatter_agent = Agent(
    name="formatter_agent",
    model=AGENT_MODEL,
    instruction="""Use the retrieved information to create a list of objects""",
    output_schema=JobPostList,
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
                "accept": crawl_node,
                "retry": request_role,
            },
        ),
        (
            request_role,
            normalize_role_node,
        ),
    ],
)
