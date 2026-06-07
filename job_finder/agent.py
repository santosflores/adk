import logging

from .models import JobPosition
from google.adk import Agent, Context, Workflow, Event
from google.adk.events import RequestInput
from google.adk.workflow import node
from google.genai import types
from typing import Any

AGENT_MODEL = "gemini-3.1-flash-lite"
logger = logging.getLogger(__name__)

position_name_capture = Agent(
    name="position_name_capture",
    model=AGENT_MODEL,
    instruction="""Your only task is to retrieve the a position (i.e role) name 
    from the end-user.

    If the job position is provided answer with the text message: "True"
    """,
    output_schema=str,
    output_key="job_position",
)

input_evaluator = Agent(
    name="input_evaluator",
    model=AGENT_MODEL,
    instruction="""You are an evaluator. Your only goal is to evaluate an input and determine 
    if it is a valid job position name. Attach a confidence value""",
    output_schema=JobPosition,
)


@node(rerun_on_resume=False)
async def get_user_approval(ctx: Context, node_input: Any):
    """Yields a RequestInput to pause the workflow and wait for user input."""
    yield RequestInput(message="Please provide a role name", response_schema=str)


@node(rerun_on_resume=True)
async def main_workflow(ctx: Context, node_input: str):
    logger.info("before calling agent position_name_capture")
    evaluation = await ctx.run_node(input_evaluator, node_input=node_input)
    while evaluation["confidence"] < 0.95:
        input = await ctx.run_node(get_user_approval)
        evaluation = await ctx.run_node(input_evaluator, node_input=input)


root_agent = Workflow(name="root_agent", edges=[("START", main_workflow)])
