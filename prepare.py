"""
Fixed evaluation harness for AITX autoresearch (Karpathy-pattern).

Mirrors karpathy/autoresearch `prepare.py`:
  - constants and data loading live here
  - the agent MUST NOT modify this file
  - `train.py` imports evaluate() / constants from here

Usage:
    python prepare.py              # verify golden dataset + print baseline constants
    python prepare.py --smoke      # one cheap dry-run without API calls
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants (fixed, do not modify)
# ---------------------------------------------------------------------------

TIME_BUDGET = 300          # wall-clock budget per experiment (seconds) — same spirit as Karpathy's 5 min
ROLLOUTS_PER_CASE = int(os.environ.get("ROLLOUTS_PER_CASE", "2"))
ACC_EPS = 0.005            # minimum accuracy gain to keep
LAT_SLACK = 1.3            # retrieval may grow at most 30% vs champion
REPO = Path(__file__).resolve().parent
GOLDEN_PATH = Path(os.environ.get("GOLDEN_DATASET", REPO / "scripts" / "golden_dataset.json"))
RESULTS_TSV = REPO / "results.tsv"
POLICY_FILE = REPO / "research" / "champion-lessons.md"

# Platforms the judge may recommend
PLATFORMS = (
    "Amazon (Direct)",
    "Amazon Marketplace Third-Party",
    "eBay",
    "Newegg",
    "Best Buy",
    "Micro Center",
)

BASE_SYSTEM = """You are a GPU purchase-decision judge for a buying-assistant team.
Given a buyer request, decide where and how to buy. Respond with ONLY a JSON
object: {"recommended_platform": str, "condition": str,
"lead_time_days": int, "reasons": [str, str]}.
Platforms: Amazon (Direct), Amazon Marketplace Third-Party, eBay, Newegg,
Best Buy, Micro Center. Be conservative about warranty and delivery claims."""


def load_golden():
    return json.loads(GOLDEN_PATH.read_text())


def score(text: str, truth: dict) -> tuple[float, bool]:
    """Rubric: 0.4 safety, 0.3 platform, 0.2 condition, 0.1 lead time."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        pred = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        pred = None
    if not pred:
        return 0.0, False
    s = 0.0
    plat = str(pred.get("recommended_platform", "")).lower()
    avoid = [a.lower() for a in truth.get("avoid_platforms", [])]
    violated = bool(plat) and any(a in plat or plat in a for a in avoid)
    if plat and not violated:
        s += 0.4
    exp = str(truth.get("expected_platform", "")).lower()
    if plat and exp and any(
        p.strip() in plat for p in exp.replace(" or ", ",").split(",") if p.strip()
    ):
        s += 0.3
    ct = str(truth.get("condition", "")).lower()
    cp = str(pred.get("condition", "")).lower()
    if ct and (ct in cp or cp in ct):
        s += 0.2
    try:
        if int(pred.get("lead_time_days", 99)) <= int(truth.get("max_lead_time_days", 99)):
            s += 0.1
    except (TypeError, ValueError):
        pass
    return round(s, 3), violated


def _chat(base: str, key: str, model: str, system: str, user: str, timeout: int = 90):
    import requests
    t0 = time.time()
    r = requests.post(
        f"{base}/chat/completions",
        timeout=timeout,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time() - t0


def judge(system: str, prompt: str) -> tuple[str, float]:
    """One rollout: NVIDIA → OpenRouter fallback."""
    nvidia = os.environ.get("NVIDIA_INFERENCE_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
    openrouter = os.environ.get("OPENROUTER_API_KEY", "")
    try:
        return _chat(
            "https://integrate.api.nvidia.com/v1",
            nvidia,
            "nvidia/nemotron-3-super-120b-a12b",
            system,
            prompt,
        )
    except Exception:
        if not openrouter:
            raise
        return _chat(
            "https://openrouter.ai/api/v1",
            openrouter,
            "nvidia/nemotron-3-super-120b-a12b",
            system,
            prompt,
        )


def evaluate(lessons: str, golden: list | None = None) -> tuple[dict, list[str]]:
    """Ground-truth metric. Do not modify — this is the val_bpb equivalent."""
    golden = golden if golden is not None else load_golden()
    system = BASE_SYSTEM + (
        "\n\nLessons learned from prior graded interactions:\n" + lessons if lessons else ""
    )
    scores, lats, violations, fails = [], [], 0, []
    t0 = time.time()
    for case in golden:
        truth = {
            "expected_platform": case.get("expected_platform", ""),
            **case.get("ground_truth", {}),
        }
        for _ in range(ROLLOUTS_PER_CASE):
            # Respect the fixed wall-clock budget (Karpathy TIME_BUDGET spirit)
            if time.time() - t0 > TIME_BUDGET:
                fails.append("time_budget_exceeded")
                break
            try:
                text, dt = judge(system, case["prompt"])
            except Exception as e:
                fails.append(f"{case['id']}: API error {e}")
                continue
            sc, viol = score(text, truth)
            scores.append(sc)
            lats.append(dt)
            violations += int(viol)
            if sc < 0.7:
                fails.append(f"{case['id']} scored {sc}: {text[:160]}")
        else:
            continue
        break
    n = len(scores) or 1
    metrics = {
        "accuracy": round(sum(scores) / n, 6),
        "retrieval_s": round(sum(lats) / (len(lats) or 1), 6),
        "deal_safety": round(100 - 100 * violations / n, 3),
        "price_regression": round(100 * violations / n, 3),
        "n": len(scores),
        "total_seconds": round(time.time() - t0, 3),
    }
    return metrics, fails


def pareto_keep(cand: dict, champ: dict, min_cases: int = 1) -> bool:
    """Keep only on Pareto improve — the keep/discard gate."""
    if cand.get("n", 0) < min_cases:
        return False
    if cand.get("accuracy", 0) < champ.get("accuracy", 0) + ACC_EPS:
        return False
    if cand.get("deal_safety", 0) < champ.get("deal_safety", 0):
        return False
    champ_lat = champ.get("retrieval_s") or 1.0
    if cand.get("retrieval_s", 999) > champ_lat * LAT_SLACK:
        return False
    return True


def ensure_results_tsv():
    if not RESULTS_TSV.exists():
        RESULTS_TSV.write_text(
            "commit\taccuracy\tretrieval_s\tdeal_safety\tstatus\tdescription\n"
        )


def append_result(commit: str, metrics: dict, status: str, description: str):
    ensure_results_tsv()
    with RESULTS_TSV.open("a") as f:
        f.write(
            f"{commit}\t{metrics.get('accuracy', 0):.6f}\t"
            f"{metrics.get('retrieval_s', 0):.3f}\t"
            f"{metrics.get('deal_safety', 0):.1f}\t"
            f"{status}\t{description.replace(chr(9), ' ')}\n"
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true", help="Print constants only; no API calls")
    args = ap.parse_args()
    golden = load_golden()
    print(f"golden_cases:     {len(golden)}")
    print(f"rollouts_per:     {ROLLOUTS_PER_CASE}")
    print(f"time_budget_s:    {TIME_BUDGET}")
    print(f"golden_path:      {GOLDEN_PATH}")
    print(f"policy_file:      {POLICY_FILE}")
    print(f"results_tsv:      {RESULTS_TSV}")
    ensure_results_tsv()
    if args.smoke:
        print("smoke_ok:         true")
        return
    print("prep_ok:          true  (evaluation harness ready; agent edits train.py only)")


if __name__ == "__main__":
    main()
