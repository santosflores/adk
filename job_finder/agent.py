import logging

from .models import JobPosition
from .tools import normalize_role as normalize_role
from google.adk import Agent, Context, Workflow, Event
from google.adk.events import EventActions, RequestInput
from google.adk.workflow import node
from google.genai import types
from typing import Any

AGENT_MODEL = "gemini-3.1-flash-lite"
CONFIDENCE_THRESHOLD = 0.95
RETRY_CONFIG = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(initial_delay=1, attempts=5),
    )
)

logger = logging.getLogger(__name__)


@node
def normalize_role_node(node_input: Any):
    if isinstance(node_input, types.Content):
        raw = node_input.parts[0].text if node_input.parts else ""
    else:
        raw = str(node_input) if node_input else ""
    return normalize_role(raw) if raw else None


@node
def check_confidence(node_input: Any):
    if node_input["confidence"] >= CONFIDENCE_THRESHOLD:
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
        ("START", normalize_role_node, input_evaluator, check_confidence),
        (
            check_confidence,
            {
                "accept": finish,
                "retry": request_role,
            },
        ),
        (request_role, normalize_role_node),
    ],
)
