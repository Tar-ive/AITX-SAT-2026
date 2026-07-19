#!/usr/bin/env python3
"""Convert episodic memory into teacher-model training files.

Reads memory/episodes.jsonl (see docs/episodic-memory.md schema) and writes:
  data/teacher/sft.jsonl          - {"input", "output"} from good episodes
  data/teacher/preferences.jsonl  - {"prompt", "chosen", "rejected"} pairs
                                    (good vs bad outcomes of the same task_type)

Usage: python3 scripts/export_teacher_dataset.py [path/to/episodes.jsonl]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "memory/episodes.jsonl")
out_dir = Path("data/teacher")
out_dir.mkdir(parents=True, exist_ok=True)

episodes = []
with src.open() as f:
    for line in f:
        line = line.strip()
        if line:
            episodes.append(json.loads(line))

sft, by_type = [], defaultdict(lambda: {"good": [], "bad": []})
for e in episodes:
    q = e.get("quality")
    if q == "good":
        sft.append({"input": e.get("request", ""), "output": e.get("outcome", "")})
    if q in ("good", "bad"):
        by_type[e.get("task_type", "chat")][q].append(e)

prefs = []
for task_type, groups in by_type.items():
    for good in groups["good"]:
        for bad in groups["bad"]:
            prefs.append({
                "prompt": f"[{task_type}] {good.get('request', '')}",
                "chosen": good.get("outcome", ""),
                "rejected": bad.get("outcome", ""),
            })

(out_dir / "sft.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in sft))
(out_dir / "preferences.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in prefs))
print(f"episodes={len(episodes)} sft={len(sft)} preference_pairs={len(prefs)}")
