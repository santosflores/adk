import logging

from google.adk.agents import Agent
from google.genai import types  # For creating message Content/Parts
from .tools import (
    get_weather,
    say_hello,
    say_goodbye,
    before_model_callback,
    before_agent_callback,
    before_tool_callback,
    after_tool_callback,
    after_agent_callback,
    after_model_callback,
)

logger = logging.getLogger(__name__)

AGENT_MODEL = "gemini-3.1-flash-lite"
RETRY_CONFIG = types.GenerateContentConfig(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(initial_delay=1, attempts=5),
    )
)

greeting_agent = None
try:
    greeting_agent = Agent(
        model=AGENT_MODEL,
        name="greeting_agent",
        instruction="You are the Greeting Agent. Your ONLY task is to provide a friendly greeting to the user. "
        "Use the 'say_hello' tool to generate the greeting. "
        "If the user provides their name, make sure to pass it to the tool. "
        "Do not engage in any other conversation or tasks.",
        description="Handles simple greetings and hellos using the 'say_hello' tool.",
        tools=[say_hello],
        generate_content_config=RETRY_CONFIG,
    )
    logger.info(
        f"✅ Agent '{greeting_agent.name}' created using model '{greeting_agent.model}'."
    )
except Exception as e:
    logger.error(f"❌ Could not create Greeting agent. Error: {e}")

farewell_agent = None
try:
    farewell_agent = Agent(
        model=AGENT_MODEL,
        name="farewell_agent",
        instruction="You are the Farewell Agent. Your ONLY task is to provide a polite goodbye message. "
        "Use the 'say_goodbye' tool when the user indicates they are leaving or ending the conversation "
        "(e.g., using words like 'bye', 'goodbye', 'thanks bye', 'see you'). "
        "Do not perform any other actions.",
        description="Handles simple farewells and goodbyes using the 'say_goodbye' tool.",
        tools=[say_goodbye],
        generate_content_config=RETRY_CONFIG,
    )
    logger.info(
        f"✅ Agent '{farewell_agent.name}' created using model '{farewell_agent.model}'."
    )
except Exception as e:
    logger.error(f"❌ Could not create Farewell agent. Error: {e}")

if greeting_agent and farewell_agent and "get_weather" in globals():
    root_agent_model = AGENT_MODEL
    root_agent = Agent(
        name="weather_agent_v2",
        model=root_agent_model,
        description="The main coordinator agent. Handles weather requests and delegates greetings/farewells to specialists.",
        instruction="You are the main Weather Agent coordinating a team. Your primary responsibility is to provide weather information. "
        "Use the 'get_weather' tool ONLY for specific weather requests (e.g., 'weather in London'). "
        "You have specialized sub-agents: "
        "1. 'greeting_agent': Handles simple greetings like 'Hi', 'Hello'. Delegate to it for these. "
        "2. 'farewell_agent': Handles simple farewells like 'Bye', 'See you'. Delegate to it for these. "
        "Analyze the user's query. If it's a greeting, delegate to 'greeting_agent'. If it's a farewell, delegate to 'farewell_agent'. "
        "If it's a weather request, handle it yourself using 'get_weather'. "
        "For anything else, respond appropriately or state you cannot handle it.",
        tools=[get_weather],
        sub_agents=[greeting_agent, farewell_agent],
        generate_content_config=RETRY_CONFIG,
        before_model_callback=before_model_callback,
        after_model_callback=after_model_callback,
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
    )
    logger.info(
        f"✅ Root Agent '{root_agent.name}' created using model '{root_agent_model}' with sub-agents: {[sa.name for sa in root_agent.sub_agents]}"
    )

else:
    logger.error(
        "❌ Cannot create root agent because one or more sub-agents failed to initialize or 'get_weather' tool is missing."
    )
    if not greeting_agent:
        logger.error(" - Greeting Agent is missing.")
    if not farewell_agent:
        logger.error(" - Farewell Agent is missing.")
    if "get_weather" not in globals():
        logger.error(" - get_weather function is missing.")
