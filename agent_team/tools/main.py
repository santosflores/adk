import datetime
import zoneinfo
import logging

logger = logging.getLogger(__name__)

from typing import Optional  # Make sure to import Optional
from zoneinfo import ZoneInfo


def get_zone_by_city(city_name: str):
    # Normalize input (replace spaces with underscores to match IANA format)
    search_term = city_name.replace(" ", "_").lower()

    # Scan through all available IANA keys
    for tz in zoneinfo.available_timezones():
        # Check if the city name matches the end of the IANA string (e.g., "America/New_York")
        if tz.lower().endswith(f"/{search_term}"):
            return ZoneInfo(tz)

    raise ValueError(f"No timezone found for city: {city_name}")


def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (77 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


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
        logger.info(f"--- Tool: say_hello called with name: {name} ---")
    else:
        greeting = (
            "Hello there!"  # Default greeting if name is None or not explicitly passed
        )
        logger.info(
            f"--- Tool: say_hello called without a specific name (name_arg_value: {name}) ---"
        )
    return greeting


def say_goodbye() -> str:
    """Provides a simple farewell message to conclude the conversation."""
    logger.info(f"--- Tool: say_goodbye called ---")
    return "Goodbye! Have a great day."
