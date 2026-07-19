---
name: scout-inspector-publisher
description: Publish the Scout research brief and Inspector review through their dedicated Discord bots.
---

# Publish Scout and Inspector stages

After the cron pipeline script provides its JSON, publish the exact Scout
research brief first, then the Inspector judgment. Use these commands; do not
include secrets, raw tool traces, or private user data:

```bash
/opt/hermes/.venv/bin/python -c "import json,urllib.request; c='<Scout research brief>'; r=urllib.request.Request('http://host.openshell.internal:8001/publish/scout',data=json.dumps({'content':c}).encode(),headers={'Content-Type':'application/json'},method='POST'); print(urllib.request.urlopen(r,timeout=15).read().decode())"
```

```bash
/opt/hermes/.venv/bin/python -c "import json,urllib.request; c='<Inspector review>'; r=urllib.request.Request('http://host.openshell.internal:8001/publish/inspector',data=json.dumps({'content':c}).encode(),headers={'Content-Type':'application/json'},method='POST'); print(urllib.request.urlopen(r,timeout=15).read().decode())"
```

If a stage publish fails because the bot or its channel is not configured,
include that failure in the final Sage report but still publish the final
report once.
