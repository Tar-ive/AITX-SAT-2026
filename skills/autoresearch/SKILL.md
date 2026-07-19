---
name: autoresearch
description: >
  Autonomous research skill for AITX (Hermes #4823 + karpathy/autoresearch).
  Git-based branch → experiment → evaluate → merge/revert loop for GPU-deal
  policy optimization (Mode 1) and knowledge research docs (Mode 2). Stdlib
  Python only; wired into scripts/auto_research_loop.py.
tags: [research, autonomous, background, ml, policy, market]
---



# Autoresearch Skill (AITX)

**Start here (Karpathy-identical filenames at repo root):**

| File | Role |
|------|------|
| [`prepare.py`](../../prepare.py) | Frozen golden-set evaluation — do not modify |
| [`train.py`](../../train.py) | Policy lessons the agent edits |
| [`program.md`](../../program.md) | Branch → edit → run → keep/discard |
| [`results.tsv`](../../results.tsv) | Experiment log |
| [`progress.png`](../../progress.png) | Running-best teaser |


Port of the Hermes Agent autoresearch design
([issue #4823](https://github.com/NousResearch/hermes-agent/issues/4823)),
adapted for the AITX GPU-buying agent stack.

## When to Use

- Continuous policy mutation against `scripts/golden_dataset.json`
- Knowledge research that builds `research.md` with evidence-backed sections
- Pause / stop / resume / status of a running research loop

## Architecture

```
skills/autoresearch/
├── SKILL.md
├── scripts/
│   ├── state.py       Atomic JSON I/O, budget checks, control
│   ├── plan.py        Experiment CRUD (investigate/deepen/verify/synthesize)
│   ├── evaluate.py    Knowledge rubric + ML metric + policy Pareto gate
│   ├── workspace.py   Git branch/merge/revert (+ --exec / Python API)
│   ├── report.py      Markdown report from state files
│   ├── registry.py    Multi-run tracking under research/registry.json
│   └── usage.py       Token/cost tracking
├── templates/
│   ├── cron_prompt.md
│   ├── watchdog_prompt.md
│   └── resume_prompt.md
├── test_e2e.py
└── test_integration.py
```

Runtime state: `research/runs/<id>/` (config, status, control, checkpoint,
plan, results.log, usage.json, workspace/). Champion lessons for the nightly
tournament stay at `research/champion-lessons.md`.

## Two Modes

| Mode | Target | Evaluation |
|------|--------|------------|
| **policy** (default) | `champion-lessons.md` | Pareto: accuracy ↑, deal_safety ≥, retrieval ≤ 1.3× |
| **knowledge** | `research.md` | E/A/D/R/N rubric (total ≥ 13, evidence ≥ 3, relevance ≥ 3) |

## Depth Tiers

| Tier | max_duration | max_tokens | max_experiments | hard_cap |
|------|-------------|------------|-----------------|----------|
| Quick | 30 min | 500K | 10 | 15 |
| Deep | 180 min | 2M | 25 | 38 |
| Unlimited | 0 (none) | 0 (none) | 30 | 45 |

## Launch (policy loop)

```bash
# Continuous loop (container / EC2 host)
OPENCODE_API_KEY=… NVIDIA_INFERENCE_API_KEY=… \
  AUTORESEARCH_MODE=policy AUTORESEARCH_DEPTH=deep CYCLE_SECS=300 \
  python3 scripts/auto_research_loop.py

# Control mid-run
python3 skills/autoresearch/scripts/state.py control research/runs/<id> --action pause
python3 skills/autoresearch/scripts/state.py control research/runs/<id> --action stop
python3 skills/autoresearch/scripts/state.py control research/runs/<id> --action none   # resume
python3 skills/autoresearch/scripts/state.py status research/runs/<id>
python3 skills/autoresearch/scripts/report.py summary research/runs/<id>
```

Dashboard: `/autoresearch` (radar snapshots from `data/radar_snapshots.json`).

## Safety Gates

- Deterministic budget limits (time / tokens / experiments)
- `control.json` pause / stop / adjust
- Stall / consecutive-failure auto-pause (3 failures)
- Git: main always holds the proven champion; failed experiments are discarded
- Nightly tournament still compares episodic / exemplar-SFT / autoresearch

## Note on infra

Terraform apply for the EC2 agent host may be unavailable from Cloud Agent
environments (SSO / local state). The loop itself runs anywhere with API keys
— local, Railway coordinator, or an already-provisioned host.
