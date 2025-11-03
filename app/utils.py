"""Utility functions for timezone handling and time parsing."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from config import settings

# Get timezone from config
_app_timezone = ZoneInfo(settings.timezone)


def get_app_timezone() -> ZoneInfo:
    """Get the configured application timezone."""
    return _app_timezone


def get_current_time() -> datetime:
    """Get current time in the configured timezone."""
    return datetime.now(_app_timezone)


def get_one_hour_ago() -> datetime:
    """Get time one hour ago in the configured timezone."""
    return get_current_time() - timedelta(hours=1)


def parse_time_to_timezone(time_str: str, target_timezone: Optional[ZoneInfo] = None) -> datetime:
    """Parse an ISO format time string and convert to the target timezone.
    
    Args:
        time_str: ISO format time string (may include Z, +00:00, or be naive)
        target_timezone: Target timezone (defaults to app timezone)
    
    Returns:
        Datetime object in the target timezone
    
    Raises:
        ValueError: If time string cannot be parsed
    """
    if target_timezone is None:
        target_timezone = _app_timezone
    
    # Normalize Z to +00:00 for parsing
    normalized = time_str.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    
    # Handle naive datetimes (assume they're in target timezone)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=target_timezone)
    else:
        # Convert to target timezone
        parsed = parsed.astimezone(target_timezone)
    
    return parsed


def format_time_for_display(dt: datetime, include_microseconds: bool = True) -> str:
    """Format a datetime for user-friendly display with timezone abbreviation.
    
    Args:
        dt: Datetime object to format
        include_microseconds: Whether to include microsecond precision
    
    Returns:
        Formatted time string (e.g., "2024-01-01 16:50:23.123456 EST")
    """
    tz_abbrev = dt.strftime("%Z")
    if include_microseconds:
        formatted = dt.strftime(f"%Y-%m-%d %H:%M:%S.%f {tz_abbrev}")
        # Remove trailing zeros and decimal point if no fractional seconds
        formatted = formatted.rstrip('0').rstrip('.')
    else:
        formatted = dt.strftime(f"%Y-%m-%d %H:%M:%S {tz_abbrev}")
    
    return formatted


def parse_and_format_time(time_str: Optional[str], default_time: Optional[datetime] = None) -> str:
    """Parse a time string and format it for display, with fallback.
    
    Args:
        time_str: ISO format time string (may be None)
        default_time: Default datetime to use if time_str is None or invalid
    
    Returns:
        Formatted time string, or fallback string if parsing fails
    """
    if not time_str:
        if default_time:
            return format_time_for_display(default_time)
        return "unknown time"
    
    try:
        parsed = parse_time_to_timezone(time_str)
        return format_time_for_display(parsed)
    except Exception as e:
        print(f"⚠️  Could not parse time '{time_str}': {e}")
        if default_time:
            return format_time_for_display(default_time)
        return time_str  # Return original string as fallback


def safe_parse_time(time_str: Optional[str], default_time: datetime) -> str:
    """Safely parse a time string to ISO format, using default if parsing fails.
    
    Args:
        time_str: ISO format time string (may be None or invalid)
        default_time: Default datetime to use if time_str is None or invalid
    
    Returns:
        ISO format time string in microseconds precision
    """
    if not time_str:
        return default_time.isoformat(timespec='microseconds')
    
    try:
        parsed = parse_time_to_timezone(time_str)
        return parsed.isoformat(timespec='microseconds')
    except Exception as e:
        print(f"⚠️  Could not parse time '{time_str}': {e}, using default")
        return default_time.isoformat(timespec='microseconds')

