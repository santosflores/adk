import asyncio

from google.adk.sessions import InMemorySessionService, Session
from google.adk.runners import Runner
from google.genai import types  # For creating message Content/Parts
from agent import weather_agent
from dotenv import load_dotenv

load_dotenv()
session_service = InMemorySessionService()

# Define constants for identifying the interaction context
APP_NAME = "weather_tutorial_app"
USER_ID = "user_1"
SESSION_ID = "session_001"  # Using a fixed ID for simplicity


async def init_session(app_name: str, user_id: str, session_id: str) -> Session:
    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    print(
        f"Session created: App='{app_name}', User='{user_id}', Session='{session_id}'"
    )
    return session


session = asyncio.run(init_session(APP_NAME, USER_ID, SESSION_ID))

runner = Runner(
    agent=weather_agent,  # The agent we want to run
    app_name=APP_NAME,  # Associates runs with our app
    session_service=session_service,  # Uses our session manager
)

if runner.agent:
    print(f"Runner created for agent '{runner.agent.name}'.")


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
    print(f"\n>>> User Query: {query}")

    # Prepare the user's message in ADK format
    content = types.Content(role="user", parts=[types.Part(text=query)])
    final_response_text = "Agent did not produce a final response."  # Default

    # Key Concept: run_async executes the agent logic and yields Events.
    # We iterate through events to find the final answer.
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        # You can uncomment the line below to see *all* events during execution
        # print(
        #     f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}"
        # )

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

    print(f"<<< Agent Response: {final_response_text}")


async def run_conversation():
    await call_agent_async(
        "What is the weather like in London?",
        runner=runner,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    await call_agent_async(
        "How about Paris?", runner=runner, user_id=USER_ID, session_id=SESSION_ID
    )  # Expecting the tool's error message

    await call_agent_async(
        "Tell me the weather in New York",
        runner=runner,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )


if __name__ == "__main__":
    try:
        asyncio.run(run_conversation())

    except Exception as e:
        print(f"An error occurred: {e}")
