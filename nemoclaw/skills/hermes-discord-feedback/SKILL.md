---
name: discord-feedback
description: Read aggregate thumbs-up and thumbs-down feedback left on recent Hermes Discord recommendations.
---

# Discord feedback

Before making a new product or retailer recommendation, Hermes may review the
recent anonymous feedback ledger:

```bash
/opt/hermes/.venv/bin/python -c "import urllib.request; print(urllib.request.urlopen('http://host.openshell.internal:8001/feedback/recent', timeout=15).read().decode())"
```

Use feedback only as a weak preference signal. Do not reveal Discord user IDs,
do not infer sensitive attributes, and do not treat a single reaction as proof
that a retailer, product, or price is good or bad. Prefer repeated feedback
patterns only when they are relevant to the current request.
