"""
Date Normalization Utility.

Parses absolute date strings, relative expressions (e.g. 'x hours ago', 'yesterday'),
and normalizes all timestamps to timezone-aware UTC datetime objects.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger

class DateNormalizer:
    """Normalizes various date formats and relative times to UTC datetime objects."""

    @staticmethod
    def normalize(date_str: str) -> Optional[datetime]:
        """
        Parses a date string or relative date string and returns a timezone-aware UTC datetime.
        Returns None if parsing fails.
        """
        if not date_str:
            return None

        date_str = date_str.strip().lower()
        now = datetime.now(timezone.utc)

        # 1. Handle relative times
        if "ago" in date_str:
            try:
                # Matches: "3 hours ago", "1 day ago", "30 mins ago", "15 minutes ago"
                match = re.search(r"(\d+)\s+(second|sec|minute|min|hour|hr|day|week|month)s?\s+ago", date_str)
                if match:
                    value = int(match.group(1))
                    unit = match.group(2)

                    if "second" in unit or "sec" in unit:
                        return now - timedelta(seconds=value)
                    elif "minute" in unit or "min" in unit:
                        return now - timedelta(minutes=value)
                    elif "hour" in unit or "hr" in unit:
                        return now - timedelta(hours=value)
                    elif "day" in unit:
                        return now - timedelta(days=value)
                    elif "week" in unit:
                        return now - timedelta(weeks=value)
                    elif "month" in unit:
                        # Estimate month as 30 days
                        return now - timedelta(days=value * 30)
            except Exception as e:
                logger.warning(f"Error parsing relative date 'ago' string '{date_str}': {e}")
                return None

        if date_str == "today":
            return now
        elif date_str == "yesterday":
            return now - timedelta(days=1)

        # 2. Try parsing standard date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d",
            "%d %b %Y",
            "%b %d, %Y",
            "%B %d, %Y",
        ]

        # Standardize Z to +00:00 to help python datetime parser
        standardized_date = date_str.upper()
        if standardized_date.endswith("Z"):
            standardized_date = standardized_date[:-1] + "+00:00"

        for fmt in formats:
            try:
                dt = datetime.strptime(standardized_date, fmt)
                # If parsed datetime has no timezone info, assume it's UTC and make it aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            except ValueError:
                continue

        logger.debug(f"Could not parse date string: '{date_str}'")
        return None
