#!/usr/bin/env python3
"""Convert a small, explicit subset of natural-language schedules to cron.

The parser intentionally does not accept arbitrary cron input.  It produces a
five-field cron expression suitable for ``hermes cron create``.
"""

from __future__ import annotations

import json
import re
import sys


DAYS = {
    "monday": "1", "tuesday": "2", "wednesday": "3", "thursday": "4",
    "friday": "5", "saturday": "6", "sunday": "0",
}
CDT_UTC_OFFSET_HOURS = 5


def parse_time(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(0?[1-9]|1[0-2])(?::([0-5][0-9]))?\s*(am|pm)", value)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(3) == "pm":
            hour += 12
        return hour, int(match.group(2) or 0)
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", value)
    if match:
        return int(match.group(1)), int(match.group(2))
    raise ValueError("time must look like '9am', '9:30 pm', or '21:30'")


def cdt_to_utc(hour: int, minute: int) -> tuple[int, int, int]:
    """Convert a CDT wall-clock time to the UTC-only Hermes scheduler."""
    total_minutes = hour * 60 + minute + CDT_UTC_OFFSET_HOURS * 60
    return (total_minutes // 60) % 24, total_minutes % 60, total_minutes // (24 * 60)


def format_time(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def parse(text: str) -> dict[str, str]:
    value = " ".join(text.strip().lower().split())
    if match := re.fullmatch(r"every (\d{1,3}) minutes?", value):
        minutes = int(match.group(1))
        if not 1 <= minutes <= 59:
            raise ValueError("minute interval must be from 1 to 59")
        return {"cron": f"*/{minutes} * * * *", "description": f"every {minutes} minutes"}
    if match := re.fullmatch(r"every (\d{1,2}) hours?", value):
        hours = int(match.group(1))
        if not 1 <= hours <= 23:
            raise ValueError("hour interval must be from 1 to 23")
        return {"cron": f"0 */{hours} * * *", "description": f"every {hours} hours"}
    if match := re.fullmatch(r"daily at (.+)", value):
        hour, minute = parse_time(match.group(1))
        utc_hour, utc_minute, _ = cdt_to_utc(hour, minute)
        return {
            "cron": f"{utc_minute} {utc_hour} * * *",
            "description": f"daily at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    if match := re.fullmatch(r"weekdays at (.+)", value):
        hour, minute = parse_time(match.group(1))
        utc_hour, utc_minute, day_offset = cdt_to_utc(hour, minute)
        utc_days = "1-5" if day_offset == 0 else "2-6"
        return {
            "cron": f"{utc_minute} {utc_hour} * * {utc_days}",
            "description": f"weekdays at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    if match := re.fullmatch(r"weekly on (" + "|".join(DAYS) + r") at (.+)", value):
        day, raw_time = match.groups()
        hour, minute = parse_time(raw_time)
        utc_hour, utc_minute, day_offset = cdt_to_utc(hour, minute)
        utc_day = (int(DAYS[day]) + day_offset) % 7
        return {
            "cron": f"{utc_minute} {utc_hour} * * {utc_day}",
            "description": f"every {day} at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    if match := re.fullmatch(r"monthly on day (\d{1,2}) at (.+)", value):
        day, raw_time = match.groups()
        day_number = int(day)
        if not 1 <= day_number <= 31:
            raise ValueError("day of month must be from 1 to 31")
        hour, minute = parse_time(raw_time)
        utc_hour, utc_minute, day_offset = cdt_to_utc(hour, minute)
        if day_offset:
            raise ValueError("monthly schedules after 6:59pm CDT cannot be converted safely; choose an earlier CDT time")
        return {
            "cron": f"{utc_minute} {utc_hour} {day_number} * *",
            "description": f"monthly on day {day_number} at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    raise ValueError(
        "supported schedules: every 15 minutes; every 2 hours; daily at 9am; "
        "weekdays at 17:30; weekly on monday at 9am; monthly on day 1 at 08:00 "
        "(all clock times are CDT)"
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: cron_parse.py '<schedule>'")
    try:
        print(json.dumps(parse(sys.argv[1])))
    except ValueError as error:
        print(json.dumps({"error": str(error)}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
