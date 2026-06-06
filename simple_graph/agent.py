import logging

from google.adk import Agent, Workflow, Event
from google.genai import types
from .tools import get_current_time, CityTime

logger = logging.getLogger(__name__)

AGENT_MODEL = "gemini-3.1-flash-lite"


def lookup_time_function(node_input: str):
    """Simulate returning the current time in the specified city."""
    return get_current_time(node_input)


city_generator_agent = Agent(
    name="city_generator_agent",
    model=AGENT_MODEL,
    instruction="Return the name of a random city from America.",
    output_schema=str,
)

logger.info(f"Created agent: {city_generator_agent.name}")

city_report_agent = Agent(
    name="city_report_agent",
    model=AGENT_MODEL,
    instruction="""Output following line:
    It is {CityTime.time_info} in {CityTime.city} right now.""",
    input_schema=CityTime,
    output_schema=str,
)


def completed_message_function(node_input: str):
    return Event(
        author="simple_agent",
        content=types.Content(
            parts=[types.Part(text=f"{node_input}\n WORKFLOW COMPLETED.")]
        ),
    )


root_agent = Workflow(
    name="root_agent",
    edges=[
        (
            "START",
            city_generator_agent,
            lookup_time_function,
            city_report_agent,
            completed_message_function,
        )
    ],
)
