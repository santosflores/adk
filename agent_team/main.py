import asyncio
import logging

from agent import root_agent
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService, Session
from google.adk.runners import Runner
from google.genai import types  # For creating message Content/Parts
from rich.logging import RichHandler

logger = logging.getLogger(__name__)

load_dotenv()


session_service = InMemorySessionService()
APP_NAME = "weather_tutorial_agent_team"
USER_ID = "user_1_agent_team"
SESSION_ID = "session_001_agent_team"
# Define initial state data - user prefers Celsius initially
initial_state = {"user_preference_temperature_unit": "Celsius"}


def extract_text(content) -> str:
    """Join all displayable text parts, skipping thoughts and non-text parts."""
    if not content or not content.parts:
        return ""
    return "".join(
        part.text
        for part in content.parts
        if part.text and not getattr(part, "thought", False)
    ).strip()


async def call_agent_async(query: str, runner, user_id, session_id):
    """Sends a query to the agent and prints the final response."""
    logger.info(f">>> User Query: {query}")

    # Prepare the user's message in ADK format
    content = types.Content(role="user", parts=[types.Part(text=query)])
    final_response_text = "Agent did not produce a final response."  # Default

    # Key Concept: run_async executes the agent logic and yields Events.
    # We iterate through events to find the final answer.
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        # You can uncomment the line below to see *all* events during execution
        logger.debug(
            f"[Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}"
        )

        # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            text = extract_text(event.content)
            if text:
                final_response_text = text
            elif (
                event.actions and event.actions.escalate
            ):  # Handle potential errors/escalations
                final_response_text = (
                    f"Agent escalated: {event.error_message or 'No specific message.'}"
                )
            # Add more checks here if needed (e.g., specific error codes)
            # break  # Stop processing events once the final response is found

    logger.info(f"<<< Agent Response: {final_response_text}")


async def run_team_conversation():
    logger.info("Testing Agent Team Delegation")

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state=initial_state,
    )
    logger.info(
        f"Session created: App='{APP_NAME}', User='{USER_ID}', Session='{SESSION_ID}'"
    )

    # Verify the initial state was set correctly
    retrieved_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    if retrieved_session:
        logger.info(f"Initial Session State: {retrieved_session.state}")
    else:
        logger.error("Error: Could not retrieve session.")
    runner_agent_team = Runner(  # Or use InMemoryRunner
        agent=root_agent, app_name=APP_NAME, session_service=session_service
    )
    logger.info(f"Runner created for agent '{root_agent.name}'.")

    # Interactions using await (correct within async def) ---
    await call_agent_async(
        query="Hello there! My name is Santos",
        runner=runner_agent_team,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    await call_agent_async(
        query="What is the weather in New York?",
        runner=runner_agent_team,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    await call_agent_async(
        query="Thanks, bye!",
        runner=runner_agent_team,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )


if __name__ == "__main__":  # Ensures this runs only when script is executed directly
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    try:
        # This creates an event loop, runs your async function, and closes the loop.
        asyncio.run(run_team_conversation())
    except Exception as e:
        logger.error(f"An error occurred: {e}")
