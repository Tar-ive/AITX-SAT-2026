"""
Autoresearch experiment script (Karpathy-pattern `train.py`).

THIS is the single file the agent edits. Everything is fair game inside
POLICY_LESSONS and the small knobs below — architecture of the *policy*,
not model weights. Evaluation is frozen in prepare.py.

Usage:
    python train.py                  # one experiment on the current policy
    python train.py --describe "..." # tag the results.tsv row

Prints a summary block (grep-friendly) then exits. The outer loop in
program.md decides keep vs discard via git, just like karpathy/autoresearch.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

from prepare import (
    POLICY_FILE,
    ROLLOUTS_PER_CASE,
    TIME_BUDGET,
    append_result,
    evaluate,
    load_golden,
    pareto_keep,
)

# ---------------------------------------------------------------------------
# Policy knobs — AGENT EDITS THESE
# ---------------------------------------------------------------------------

# Primary artifact under optimization (our "model weights" are these lessons).
# Keep ≤20 tight generalized bullets. No golden-set IDs / memorized answers.
POLICY_LESSONS = """# Champion lessons (autoresearch)

- Prefer **online-fulfillable** listings (Amazon Direct, Newegg, Best Buy ship-to-home).
- **Micro Center member / in-store-only** prices are useful context but must not be the primary recommendation unless the buyer explicitly opts into local pickup.
- When Micro Center undercuts online by a wide margin, mention it as an optional local pickup — never as the only "best place to buy."
- Prefer sealed OEM / manufacturer warranty over marketplace third-party for warranty-critical GPUs.
- Reject Wish and other too-good-to-be-true platforms for GPUs and RAM.
- Keep lessons short (≤20 bullets); long memory slows retrieval.
- Lead-time claims must be conservative; do not promise weekend delivery without evidence.
- Counterfeit / gray-market cues: new-seller + deep discount + no warranty → avoid.
"""

# Optional experiment tags the agent can flip while iterating
ONLINE_FIRST = True          # if True, reinforce online-fulfillable preference
MAX_LESSON_BULLETS = 20      # soft cap — compress if you exceed this
TEMPERATURE = 0              # judge sampling (prepare.judge uses 0; kept for clarity)


# ---------------------------------------------------------------------------
# Experiment runner (usually leave alone; prepare.py owns the metric)
# ---------------------------------------------------------------------------

def _git_short() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "0000000"


def _load_champion_metrics(path: Path) -> dict | None:
    """Best prior keep row from results.tsv, if any."""
    if not path.exists():
        return None
    best = None
    for line in path.read_text().splitlines()[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5 or parts[4] not in ("keep", "baseline"):
            continue
        try:
            row = {
                "accuracy": float(parts[1]),
                "retrieval_s": float(parts[2]),
                "deal_safety": float(parts[3]),
            }
        except ValueError:
            continue
        if best is None or row["accuracy"] > best["accuracy"]:
            best = row
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--describe", default="train.py policy eval", help="results.tsv description")
    ap.add_argument("--write-policy", action="store_true",
                    help="Sync POLICY_LESSONS to research/champion-lessons.md before eval")
    args = ap.parse_args()

    lessons = POLICY_LESSONS.strip() + "\n"
    if ONLINE_FIRST and "online-fulfillable" not in lessons.lower():
        lessons += "- Prefer online-fulfillable storefronts over in-store-only member pricing.\n"
    bullets = [ln for ln in lessons.splitlines() if ln.strip().startswith("-")]
    if len(bullets) > MAX_LESSON_BULLETS:
        # Simplicity criterion: truncate rather than ship a bloated policy
        kept = bullets[:MAX_LESSON_BULLETS]
        head = [ln for ln in lessons.splitlines() if not ln.strip().startswith("-")]
        lessons = "\n".join(head + kept) + "\n"

    if args.write_policy:
        POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        POLICY_FILE.write_text(lessons)

    golden = load_golden()
    t0 = time.time()
    metrics, fails = evaluate(lessons, golden)
    # Agent-regression proxy: fraction of fails (Hermes episodic pain)
    metrics["agent_regression"] = round(min(1.0, len(fails) / max(1, len(golden) * ROLLOUTS_PER_CASE)), 6)

    # Fixed-budget report (Karpathy-style block — grep these keys from run.log)
    print("---")
    print(f"accuracy:          {metrics['accuracy']:.6f}")
    print(f"retrieval_s:       {metrics['retrieval_s']:.6f}")
    print(f"deal_safety:       {metrics['deal_safety']:.3f}")
    print(f"price_regression:  {metrics['price_regression']:.3f}")
    print(f"agent_regression:  {metrics['agent_regression']:.6f}")
    print(f"n:                 {metrics['n']}")
    print(f"training_seconds:  {metrics['total_seconds']:.1f}")
    print(f"total_seconds:     {time.time() - t0:.1f}")
    print(f"time_budget:       {TIME_BUDGET}")
    print(f"lesson_bullets:    {len(bullets)}")
    print(f"online_first:      {ONLINE_FIRST}")
    if fails[:5]:
        print(f"sample_fails:      {fails[:5]}")

    # Auto-log vs previous champion for convenience; program.md still owns git keep/discard
    champ = _load_champion_metrics(Path("results.tsv"))
    status = "baseline" if champ is None else (
        "keep" if pareto_keep(metrics, champ, min_cases=max(1, int(0.6 * len(golden) * ROLLOUTS_PER_CASE)))
        else "discard"
    )
    append_result(_git_short(), metrics, status, args.describe)
    print(f"status:            {status}")
    return 0 if status in ("keep", "baseline") else 1


if __name__ == "__main__":
    raise SystemExit(main())
