# autoresearch

This is an experiment to have the LLM do its own research — AITX edition.

Adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch): same
branch → edit → run → keep/discard loop. The "model" here is a GPU-purchase
**policy lessons file** scored on a frozen golden set (accuracy ↑, retrieval ↓,
deal safety ↑), not `val_bpb`.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `jul19`). The branch `autoresearch/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current main.
3. **Read the in-scope files**: The loop surface is deliberately small. Read these files for full context:
   - `README.md` — repository context + data plane (EC2 → Railway → Vercel).
   - `prepare.py` — fixed constants, golden dataset, evaluation. **Do not modify.**
   - `train.py` — the file you modify. Policy lessons + small knobs.
4. **Verify data exists**: `scripts/golden_dataset.json` must be present. Confirm with `python prepare.py --smoke`.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row if missing (`python prepare.py` does this). The baseline will be recorded after the first run.
6. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment evaluates the policy in `train.py` against the frozen golden set via `prepare.evaluate`. Launch:

```bash
python train.py --describe "short hypothesis" --write-policy > run.log 2>&1
```

**What you CAN do:**
- Modify `train.py` — this is the only file you edit. Fair game: `POLICY_LESSONS`, `ONLINE_FIRST`, `MAX_LESSON_BULLETS`, and any helper logic that still calls `prepare.evaluate`.

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It contains the fixed evaluation, golden loader, and time budget.
- Install new packages beyond `pyproject.toml` / `requirements.txt`.
- Modify the evaluation harness or memorize golden-set answers into the lessons.
- Recommend Micro Center **in-store / member-only** prices as the primary buy unless the user opts into local pickup (online-first constraint).

**The goal is simple: raise accuracy, keep deal_safety from falling, and keep retrieval_s from blowing up.** Pareto gate (in `prepare.pareto_keep`):

- `accuracy` must rise by ≥ `ACC_EPS` (0.005)
- `deal_safety` must not drop
- `retrieval_s` ≤ `1.3 ×` champion

**Simplicity criterion**: All else equal, simpler is better. A tiny accuracy bump that adds 20 vague bullets? Discard. Deleting a bullet and holding accuracy? Keep.

**The first run**: Always establish the baseline — run `train.py` as-is before mutating.

## Output format

Once the script finishes it prints a summary like this:

```
---
accuracy:          0.593300
retrieval_s:       2.840000
deal_safety:       100.000
price_regression:  0.000
agent_regression:  0.055000
n:                 30
training_seconds:  45.2
total_seconds:     46.1
time_budget:       300
lesson_bullets:    8
online_first:      True
status:            keep
```

Extract key metrics:

```bash
grep -E "^(accuracy|retrieval_s|deal_safety|status):" run.log
```

## Logging results

When an experiment is done, confirm the row in `results.tsv` (tab-separated):

```
commit	accuracy	retrieval_s	deal_safety	status	description
```

Statuses: `keep`, `discard`, `crash`, or `baseline`.

`train.py` appends a row automatically; you still own the **git** keep/discard.

## The experiment loop

LOOP FOREVER:

1. Look at git state (branch / commit).
2. Edit `train.py` with an experimental idea (usually `POLICY_LESSONS`).
3. `git add train.py && git commit -m "exp: <hypothesis>"`
4. Run: `python train.py --describe "<hypothesis>" --write-policy > run.log 2>&1`
5. Read metrics from `run.log`.
6. If accuracy Pareto-improves → **keep** the commit (advance the branch).
7. If equal/worse/crash → `git reset --hard HEAD~1` (**discard**).
8. Log honesty in `results.tsv` (already appended; fix status by hand if the process crashed).

**Timeout**: If a run exceeds ~2× `TIME_BUDGET` (10 min), kill it and treat as `crash`.

**NEVER STOP**: Once the loop has begun, do not pause to ask whether to continue. The human may be asleep. Autonomous until interrupted.

## Long-running host

On the always-on EC2 agent host you may also launch the continuous wrapper (same gate, posts to Railway):

```bash
CYCLE_SECS=300 COORDINATOR_URL=https://nemoclaw-coordinator-api-production.up.railway.app \
  python scripts/auto_research_loop.py
```

That wrapper still treats `train.py` / `research/champion-lessons.md` as the champion artifact and follows the same prepare.py metrics.
