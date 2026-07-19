---
name: hermes-episode-writer
description: Store a concise, feedback-grounded Hermes learning episode for other agents to read from Supabase.
---

# Hermes episodic learning

After a meaningful Discord job is complete, Hermes may write one compact
episode to the trusted proxy. Write an episode only when there is a useful
learning signal: a 👍/👎 reaction, explicit correction, successful outcome, or
clear failure. Never store raw transcripts, Discord IDs, product credentials,
API keys, passwords, connection strings, or chain-of-thought.

```bash
/opt/hermes/.venv/bin/python -c "import json,urllib.request; episode={'task_type':'shopping_research','request':'concise user need','agent_chain':['hermes'],'outcome':'concise delivered result','feedback':{'signal':'thumbs_up'},'quality':'good','lesson':'generalized, evidence-backed lesson'}; request=urllib.request.Request('http://host.openshell.internal:8001/episodes',data=json.dumps(episode).encode(),headers={'Content-Type':'application/json'},method='POST'); print(urllib.request.urlopen(request,timeout=15).read().decode())"
```

The endpoint accepts only structured episode fields and writes only to
`public.episodes`. Other agents retain read-only database access and can use
the existing `supabase-readonly` skill to query relevant lessons.
