import logging

from google.adk import Agent, Context, Workflow
from google.adk.workflow import node
from typing import Any

AGENT_MODEL = "gemini-3.1-flash-lite"
logger = logging.getLogger(__name__)


@node(name="hello_node")
def hello_node(node_input: Any):
    logger.info(f"node_input: {node_input}")
    return "Hello world"


@node(rerun_on_resume=True)
async def workflow(ctx: Context, node_input: str):
    result = await ctx.run_node(hello_node, node_input=node_input)
    logger.info(result)
    return result


root_agent = Workflow(
    name="root_agent",
    edges=[("START", workflow)],
)
