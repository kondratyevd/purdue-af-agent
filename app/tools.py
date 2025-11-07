from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from config import settings

_app_timezone = ZoneInfo(settings.timezone)


def _parse_to_timezone(time_str: str) -> datetime:
    """Parse time string to app timezone.

    Handles both raw ISO 8601 strings and annotated strings (e.g., "Current time: 2025-11-04T11:57:20.161562-05:00").
    """
    # Extract actual time value if string is annotated (contains ": ")
    if ": " in time_str:
        time_str = time_str.split(": ", 1)[-1]
    normalized = time_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_app_timezone)
    else:
        dt = dt.astimezone(_app_timezone)
    return dt


def _format_display(dt: datetime, include_microseconds: bool = True) -> str:
    """Format datetime for user-friendly display."""
    tz_abbrev = dt.strftime("%Z")
    if include_microseconds:
        formatted = dt.strftime(f"%Y-%m-%d %H:%M:%S.%f {tz_abbrev}")
        formatted = formatted.rstrip("0").rstrip(".")
    else:
        formatted = dt.strftime(f"%Y-%m-%d %H:%M:%S {tz_abbrev}")
    return formatted


@tool(parse_docstring=True)
def get_current_datetime_info_tool() -> str:
    """Get comprehensive current datetime information in the configured timezone.

    Provides: ISO 8601 timestamp, weekday name (Monday-Sunday), date, time, and timezone.
    Essential for: Determining current weekday before calculating relative days (e.g., "last Friday").

    Returns:
        A string containing current ISO 8601 timestamp, weekday name, and other datetime details.
    """
    now = datetime.now(_app_timezone)
    iso_time = now.isoformat(timespec="microseconds")
    weekday = now.strftime("%A")
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    tz_abbrev = now.strftime("%Z")

    return (
        f"Current datetime info:\n"
        f"  ISO 8601: {iso_time}\n"
        f"  Weekday: {weekday}\n"
        f"  Date: {date_str}\n"
        f"  Time: {time_str}\n"
        f"  Timezone: {tz_abbrev}"
    )


@tool(parse_docstring=True)
def get_one_hour_ago_tool() -> str:
    """Get the time one hour ago in the configured timezone.

    Returns:
        ISO 8601 string with microseconds in the configured timezone.
    """
    one_hour_ago = (datetime.now(_app_timezone) - timedelta(hours=1)).isoformat(
        timespec="microseconds"
    )
    return f"Time one hour ago: {one_hour_ago}"


@tool(parse_docstring=True)
def parse_time_to_timezone_tool(time_str: str) -> str:
    """Parse an ISO 8601 time string and convert it to the configured timezone.

    Args:
        time_str: Time string in ISO 8601 format (supports Z, offsets, or naive).

    Returns:
        ISO 8601 string with microseconds in the configured timezone.
    """
    converted_time = _parse_to_timezone(time_str).isoformat(timespec="microseconds")
    return f"Converted time to app timezone: {converted_time}"


@tool(parse_docstring=True)
def format_time_for_display_tool(
    time_str: str, include_microseconds: bool = True
) -> str:
    """Format an ISO 8601 time for user-friendly display with timezone.

    Args:
        time_str: ISO 8601 time string to format.
        include_microseconds: Whether to show fractional seconds.

    Returns:
        Readable string like "2024-01-01 12:34:56.123456 EST".
    """
    formatted = _format_display(_parse_to_timezone(time_str), include_microseconds)
    return f"Formatted time: {formatted}"


@tool(parse_docstring=True)
def parse_and_format_time_tool(
    time_str: Optional[str], default_time: Optional[str] = None
) -> str:
    """Parse a time string and format it for display; fallback to default when invalid.

    Args:
        time_str: ISO 8601 time string (may be None or invalid).
        default_time: ISO 8601 fallback time string when parsing fails (optional).

    Returns:
        Readable string suitable for user display.
    """
    if not time_str:
        formatted = (
            _format_display(_parse_to_timezone(default_time))
            if default_time
            else "unknown time"
        )
        return f"Parsed and formatted time (using default): {formatted}"

    try:
        formatted = _format_display(_parse_to_timezone(time_str))
        return f"Parsed and formatted time: {formatted}"
    except Exception as e:
        print(f"⚠️  Could not parse time '{time_str}': {e}")
        formatted = (
            _format_display(_parse_to_timezone(default_time))
            if default_time
            else time_str
        )
        return f"Parsed and formatted time (using fallback): {formatted}"


@tool(parse_docstring=True)
def safe_parse_time_tool(time_str: Optional[str], default_time: str) -> str:
    """Safely parse a time string; on failure, return the provided default time.

    Args:
        time_str: ISO 8601 time string (may be None or invalid).
        default_time: ISO 8601 fallback time string used when parsing fails.

    Returns:
        ISO 8601 string with microseconds in the configured timezone.
    """
    try:
        parsed_time = _parse_to_timezone(
            time_str if time_str else default_time
        ).isoformat(timespec="microseconds")
        if not time_str:
            return f"Parsed time (using default): {parsed_time}"
        return f"Parsed time: {parsed_time}"
    except Exception as e:
        print(f"⚠️  Could not parse time '{time_str}': {e}, using default")
        parsed_time = _parse_to_timezone(default_time).isoformat(
            timespec="microseconds"
        )
        return f"Parsed time (using fallback): {parsed_time}"


@tool(parse_docstring=True)
def add_time_delta_tool(time_str: str, amount: int, unit: str) -> str:
    """Add a time delta to a timestamp and return ISO 8601 in app timezone.

    Note: For relative day calculations, first use get_current_datetime_info_tool
    to determine the current weekday, then calculate the correct number of days to add/subtract.

    Args:
        time_str: ISO 8601 time string (supports Z, offsets, or naive).
        amount: Amount to add (can be negative).
        unit: One of: seconds, minutes, hours, days, weeks, years.

    Returns:
        ISO 8601 string with microseconds in the configured timezone.
    """
    base = _parse_to_timezone(time_str)
    unit_lower = unit.lower()
    if unit_lower == "seconds":
        delta = timedelta(seconds=amount)
    elif unit_lower == "minutes":
        delta = timedelta(minutes=amount)
    elif unit_lower == "hours":
        delta = timedelta(hours=amount)
    elif unit_lower == "days":
        delta = timedelta(days=amount)
    elif unit_lower == "weeks":
        delta = timedelta(weeks=amount)
    elif unit_lower in ("year", "years"):
        # For years, we need to handle leap years, so we add to the year component
        # Use replace() to add years, which handles leap years correctly
        try:
            result_time = base.replace(year=base.year + amount).isoformat(
                timespec="microseconds"
            )
        except ValueError:
            # Handle leap year edge case (Feb 29 -> Feb 28 in non-leap year)
            result_time = base.replace(year=base.year + amount, day=28).isoformat(
                timespec="microseconds"
            )
        unit_plural = "year" if abs(amount) == 1 else "years"
        return f"Time after adding {amount} {unit_plural}: {result_time}"
    else:
        return f"Error: Unsupported unit '{unit}'. Supported units are: seconds, minutes, hours, days, weeks, years."

    result_time = (base + delta).isoformat(timespec="microseconds")
    unit_plural = unit if abs(amount) != 1 else unit.rstrip("s")
    return f"Time after adding {amount} {unit_plural}: {result_time}"


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on progress and decision-making.

    Use this tool after each tool call to analyze results and plan next steps systematically.
    This creates a deliberate pause in the workflow for quality decision-making.

    When to use:
    - After receiving tool results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing gaps: What specific information am I still missing?
    - Before concluding: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence for a good answer?
    4. Strategic decision - What specific tool should I call next, or should I provide my answer?

    CRITICAL: After using think_tool, you MUST immediately act on your reflection. If your reflection
    identifies that you need to verify, calculate, or check something, you MUST call the appropriate
    tool in your next response. Do not just reflect and stop - always follow through with actions.

    Args:
        reflection: Your detailed reflection on progress, findings, gaps, and next steps.
    """
    return f"Reflection recorded: {reflection}"


@tool(parse_docstring=True)
def subtract_time_delta_tool(time_str: str, amount: int, unit: str) -> str:
    """Subtract a time delta from a timestamp and return ISO 8601 in app timezone.

    Note: For relative day calculations, first use get_current_datetime_info_tool
    to determine the current weekday, then calculate the correct number of days to subtract based on
    the weekday difference (not a fixed number).

    Args:
        time_str: ISO 8601 time string (supports Z, offsets, or naive).
        amount: Amount to subtract (can be negative; positive means subtract).
        unit: One of: seconds, minutes, hours, days, weeks, years.

    Returns:
        ISO 8601 string with microseconds in the configured timezone.
    """
    result = add_time_delta_tool.invoke(
        {
            "time_str": time_str,
            "amount": -amount,
            "unit": unit,
        }
    )
    # Extract the time from the annotated result and re-annotate for subtraction
    result_time = result.split(": ")[-1] if ": " in result else result
    unit_plural = unit if abs(amount) != 1 else unit.rstrip("s")
    return f"Time after subtracting {amount} {unit_plural}: {result_time}"


@tool(parse_docstring=True)
def check_weekday_tool(date_str: str) -> str:
    """Check the weekday of a given date.

    **CRITICAL: You MUST ALWAYS use this tool whenever you attempt to infer or calculate a weekday.**
    This tool is MANDATORY when working with relative date references that involve weekdays
    (e.g., "last Friday", "next Tuesday", "this Monday"). After calculating what you believe
    to be the correct date for a weekday reference, you MUST call this tool to verify that
    the computed date actually falls on the expected weekday. Do not skip this verification step.

    Use this tool to validate assumptions about the weekday of a specific date.
    This is especially useful when calculating relative dates (e.g., "last Friday")
    to verify that the computed date actually falls on the expected weekday.

    Args:
        date_str: Date string in ISO 8601 format (e.g., "2025-11-01" or "2025-11-01T12:00:00-05:00").
                  Can be a date-only string or a full datetime string. If a datetime is provided,
                  only the date portion is used to determine the weekday.

    Returns:
        A string indicating the weekday name (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday)
        and the date in a readable format.

    Raises:
        ValueError: If the date string cannot be parsed.
    """
    if not date_str:
        raise ValueError("date_str is required and cannot be empty")

    try:
        # Parse the date string - handles both date-only and datetime strings
        dt = _parse_to_timezone(date_str)
        weekday = dt.strftime("%A")
        date_formatted = dt.strftime("%Y-%m-%d")

        return f"Date {date_formatted} is a {weekday}"
    except Exception as e:
        raise ValueError(f"Failed to parse date '{date_str}': {e}")


TOOLS = [
    get_current_datetime_info_tool,
    get_one_hour_ago_tool,
    parse_time_to_timezone_tool,
    format_time_for_display_tool,
    parse_and_format_time_tool,
    safe_parse_time_tool,
    add_time_delta_tool,
    subtract_time_delta_tool,
    check_weekday_tool,
]

# Create a mapping of tool names to tools for easy lookup
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

# Pre-computed formatted tool list for prompts (name: description format)
TOOL_LIST = "\n".join([f"- {tool.name}: {tool.description}" for tool in TOOLS])
