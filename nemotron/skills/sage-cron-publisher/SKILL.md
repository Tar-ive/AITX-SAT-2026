---
name: sage-cron-publisher
description: Publish completed Hermes cron-job summaries to Discord through Sage.
---

# Publish a cron result through Sage

After a scheduled Hermes job completes, send a concise report to Sage. Include
the task name, status, key findings, and any action needed. Do not include API
keys, connection strings, raw tool traces, or private user data.

Use this command:

```bash
/opt/hermes/.venv/bin/python -c "import json, urllib.request; report='JOB: <name>\nSTATUS: complete\nSUMMARY: <concise result>'; request=urllib.request.Request('http://host.openshell.internal:8001/publish', data=json.dumps({'content': report}).encode(), headers={'Content-Type':'application/json'}, method='POST'); print(urllib.request.urlopen(request, timeout=15).read().decode())"
```

If the job fails, use `STATUS: failed` and state what failed plus the recommended
next action. Publish once per completed run; do not post intermediate chatter.
