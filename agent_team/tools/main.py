import datetime
import zoneinfo
import logging

from google.adk.tools import ToolContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents.callback_context import CallbackContext

from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def get_zone_by_city(city_name: str):
    # Normalize input (replace spaces with underscores to match IANA format)
    search_term = city_name.replace(" ", "_").lower()

    # Scan through all available IANA keys
    for tz in zoneinfo.available_timezones():
        # Check if the city name matches the end of the IANA string (e.g., "America/New_York")
        if tz.lower().endswith(f"/{search_term}"):
            return ZoneInfo(tz)

    raise ValueError(f"No timezone found for city: {city_name}")


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    agent_name = callback_context.agent_name
    logger.info(f"Callback: before_model_callback running for agent: {agent_name}")
    logger.debug(f"callback_context: {vars(callback_context)}")


def get_weather(city: str, tool_context: ToolContext) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    preferred_unit = tool_context.state.get("user_preference_temperature_unit", None)
    city_normalized = city.lower().replace(" ", "")
    logger.info(f"Preferred unit: {preferred_unit} City Normalized: {city_normalized}")
    # Mock weather data (always stored in Celsius internally)
    mock_weather_db = {
        "newyork": {"temp_c": 25, "condition": "sunny"},
        "london": {"temp_c": 15, "condition": "cloudy"},
        "tokyo": {"temp_c": 18, "condition": "light rain"},
    }

    if city_normalized in mock_weather_db:
        data = mock_weather_db[city_normalized]
        temp_c = data["temp_c"]
        condition = data["condition"]

        # Format temperature based on state preference
        if preferred_unit == "Fahrenheit":
            temp_value = (temp_c * 9 / 5) + 32  # Calculate Fahrenheit
            temp_unit = "°F"
        else:  # Default to Celsius
            temp_value = temp_c
            temp_unit = "°C"

        report = f"The weather in {city.capitalize()} is {condition} with a temperature of {temp_value:.0f}{temp_unit}."
        result = {"status": "success", "report": report}
        logger.info(f"Tool: Generated report in {preferred_unit}. Result: {result}")

        # Example of writing back to state (optional for this tool)
        tool_context.state["last_city_checked_stateful"] = city
        logger.info(f"Tool: Updated state 'last_city_checked_stateful': {city}")

        return result
    else:
        # Handle city not found
        error_msg = f"Sorry, I don't have weather information for '{city}'."
        logger.error(f"Tool: City '{city}' not found.")
        return {"status": "error", "error_message": error_msg}


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """
    try:
        tz = get_zone_by_city(city)
        now = datetime.datetime.now(tz)
        report = (
            f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
        )
        return {"status": "success", "report": report}
    except:
        return {
            "status": "error",
            "error_message": (f"Sorry, I don't have timezone information for {city}."),
        }


def say_hello(name: Optional[str] = None) -> str:
    """Provides a simple greeting. If a name is provided, it will be used.

    Args:
        name (str, optional): The name of the person to greet. Defaults to a generic greeting if not provided.

    Returns:
        str: A friendly greeting message.
    """
    if name:
        greeting = f"Hello, {name}!"
        logger.info(f"Tool: say_hello called with name: {name}")
    else:
        greeting = (
            "Hello there!"  # Default greeting if name is None or not explicitly passed
        )
        logger.info(
            f"Tool: say_hello called without a specific name (name_arg_value: {name})"
        )
    return greeting


def say_goodbye() -> str:
    """Provides a simple farewell message to conclude the conversation."""
    logger.info(f"Tool: say_goodbye called")
    return "Goodbye! Have a great day."
