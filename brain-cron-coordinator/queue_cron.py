#!/usr/bin/env python3
"""Submit a Brain-confirmed cron request to the local Hermes broker."""

import json
import sys
from urllib.request import Request, urlopen


if len(sys.argv) != 6:
    raise SystemExit("usage: queue_cron.py <schedule> <timezone> <name> <prompt> <requester>")

payload = {
    "schedule": sys.argv[1],
    "timezone": sys.argv[2],
    "name": sys.argv[3],
    "prompt": sys.argv[4],
    "requested_by": sys.argv[5],
    "confirmed": True,
}
request = Request(
    "http://host.openshell.internal:8001/cron-requests",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
print(urlopen(request, timeout=15).read().decode())
