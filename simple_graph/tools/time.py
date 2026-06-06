import datetime
import zoneinfo

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