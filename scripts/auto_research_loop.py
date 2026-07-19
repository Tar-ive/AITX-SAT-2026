#!/usr/bin/env python3
"""Autoresearch loop (karpathy/autoresearch pattern) for the GPU-deal policy.

Each cycle, a researcher model (opencode zen) mutates the lessons file — our
"program.md" — then the loop evaluates the candidate on the frozen golden
dataset across FOUR objectives and keeps it only if it Pareto-improves:

  accuracy      decision_quality mean          - must go UP
  retrieval     mean seconds per answer        - must stay LOW
  deal_safety   100 - forbidden-platform hits  - price regression must NOT happen
  stability     accuracy vs champion delta     - model regression must NOT happen

Snapshots stream to data/radar_snapshots.json (the dashboard radar reads it)
and to the coordinator API. Runs forever in a container; stdlib + requests.
Env: OPENCODE_API_KEY (researcher), NVIDIA_INFERENCE_API_KEY (+ optional
OPENROUTER_API_KEY fallback), optional COORDINATOR_URL, CYCLE_SECS.
"""

import json
import os
import re
import time
from pathlib import Path

import requests

REPO = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parents[1]))
GOLDEN = json.loads((REPO / "scripts" / "golden_dataset.json").read_text())
SNAPSHOTS = REPO / "data" / "radar_snapshots.json"
RESEARCH_DIR = REPO / "research"
CHAMPION = RESEARCH_DIR / "champion-lessons.md"
CYCLE_SECS = int(os.environ.get("CYCLE_SECS", "300"))
ROLLOUTS_PER_CASE = int(os.environ.get("ROLLOUTS_PER_CASE", "2"))

NVIDIA_KEY = os.environ.get("NVIDIA_INFERENCE_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENCODE_KEY = os.environ["OPENCODE_API_KEY"]
COORD = os.environ.get("COORDINATOR_URL", "").rstrip("/")

BASE_SYSTEM = """You are a GPU purchase-decision judge for a buying-assistant team.
Given a buyer request, decide where and how to buy. Respond with ONLY a JSON
object: {"recommended_platform": str, "condition": str,
"lead_time_days": int, "reasons": [str, str]}.
Platforms: Amazon (Direct), Amazon Marketplace Third-Party, eBay, Newegg,
Best Buy, Micro Center. Be conservative about warranty and delivery claims."""


def chat(base, key, model, system, user, timeout=90):
    t0 = time.time()
    r = requests.post(f"{base}/chat/completions", timeout=timeout,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time() - t0


def judge(system, prompt):
    """One rollout with NVIDIA -> OpenRouter fallback. Returns (text, secs)."""
    try:
        return chat("https://integrate.api.nvidia.com/v1", NVIDIA_KEY,
                    "nvidia/nemotron-3-super-120b-a12b", system, prompt)
    except Exception:
        if not OPENROUTER_KEY:
            raise
        return chat("https://openrouter.ai/api/v1", OPENROUTER_KEY,
                    "nvidia/nemotron-3-super-120b-a12b", system, prompt)


def score(text, truth):
    """Same rubric as environments/gpu_deal_judge: 0.4 safety, 0.3 platform,
    0.2 condition, 0.1 lead time. Returns (score, violated)."""
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
    if plat and exp and any(p.strip() in plat for p in exp.replace(" or ", ",").split(",") if p.strip()):
        s += 0.3
    ct, cp = str(truth.get("condition", "")).lower(), str(pred.get("condition", "")).lower()
    if ct and (ct in cp or cp in ct):
        s += 0.2
    try:
        if int(pred.get("lead_time_days", 99)) <= int(truth.get("max_lead_time_days", 99)):
            s += 0.1
    except (TypeError, ValueError):
        pass
    return round(s, 3), violated


def evaluate(lessons: str):
    system = BASE_SYSTEM + ("\n\nLessons learned from prior graded interactions:\n" + lessons if lessons else "")
    scores, lats, violations, fails = [], [], 0, []
    for case in GOLDEN:
        truth = {"expected_platform": case.get("expected_platform", ""), **case.get("ground_truth", {})}
        for _ in range(ROLLOUTS_PER_CASE):
            try:
                text, dt = judge(system, case["prompt"])
            except Exception as e:
                fails.append(f"{case['id']}: API error {e}")
                continue
            sc, viol = score(text, truth)
            scores.append(sc)
            lats.append(dt)
            violations += viol
            if sc < 0.7:
                fails.append(f"{case['id']} scored {sc}: {text[:160]}")
    n = len(scores) or 1
    return {"accuracy": round(sum(scores) / n, 4),
            "retrieval_s": round(sum(lats) / (len(lats) or 1), 2),
            "deal_safety": round(100 - 100 * violations / n, 1),
            "n": len(scores)}, fails


def mutate(champion_lessons, history, fails):
    prompt = f"""You are the researcher in an autoresearch loop optimizing a GPU
purchase-decision policy. The policy IS the lessons file below (like
autoresearch's program.md). Objectives: accuracy UP, response length SHORT
(long lessons slow retrieval), zero forbidden-platform picks, no regression.

CURRENT CHAMPION LESSONS:
{champion_lessons or '(empty)'}

RECENT SCOREBOARD (newest last): {json.dumps(history[-4:])}

FAILURES FROM LAST EVALUATION:
{chr(10).join(fails[:12]) or '(none)'}

Write an improved lessons file: <=20 tight bullet rules, generalized from the
failures, no test-case IDs or memorized answers, markdown bullets only.
Reply with ONLY the new lessons file content."""
    sys_msg = "You improve policy instruction files. Output only the file content."
    try:
        text, _ = chat("https://opencode.ai/zen/v1", OPENCODE_KEY,
                       os.environ.get("RESEARCHER_MODEL", "nemotron-3-ultra-free"),
                       sys_msg, prompt, timeout=240)
    except Exception:
        # opencode credits/outage: fall back to NVIDIA (then OpenRouter via judge path)
        text, _ = chat("https://integrate.api.nvidia.com/v1", NVIDIA_KEY,
                       "nvidia/nemotron-3-super-120b-a12b", sys_msg, prompt, timeout=240)
    # strip <think> blocks reasoning models may emit
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


def snapshot(entry):
    hist = json.loads(SNAPSHOTS.read_text()) if SNAPSHOTS.exists() else []
    hist.append(entry)
    SNAPSHOTS.parent.mkdir(exist_ok=True)
    SNAPSHOTS.write_text(json.dumps(hist, indent=1))
    if COORD:
        for path in ("/api/radar", "/api/evaluations"):
            try:
                requests.post(f"{COORD}{path}", timeout=15,
                              json={"source": "autoresearch-loop", **entry})
            except requests.RequestException:
                pass
    return hist


def resync_coordinator():
    """Railway storage is ephemeral: on start, re-POST the full local history
    so a redeploy that wiped the coordinator self-heals within one cycle."""
    if not COORD or not SNAPSHOTS.exists():
        return
    try:
        hist = json.loads(SNAPSHOTS.read_text())
        requests.post(f"{COORD}/api/radar", timeout=20,
                      json=[{"source": "autoresearch-loop", **e} for e in hist])
        print(f"[autoresearch] resynced {len(hist)} snapshots to coordinator", flush=True)
    except (requests.RequestException, json.JSONDecodeError):
        pass


def main():
    RESEARCH_DIR.mkdir(exist_ok=True)
    resync_coordinator()
    champion = CHAMPION.read_text() if CHAMPION.exists() else ""
    print("[autoresearch] evaluating champion baseline...", flush=True)
    champ_metrics, fails = evaluate(champion)
    history = snapshot({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "version": "champion-0", "role": "champion", **champ_metrics})
    cycle = 0
    while True:
        cycle += 1
        print(f"[autoresearch] cycle {cycle}: mutating policy...", flush=True)
        try:
            candidate = mutate(champion, history, fails)
        except Exception as e:
            print(f"[autoresearch] researcher call failed: {e}; retrying next cycle", flush=True)
            time.sleep(CYCLE_SECS)
            continue
        cand_metrics, cand_fails = evaluate(candidate)
        accepted = (cand_metrics["n"] >= 0.6 * len(GOLDEN) * ROLLOUTS_PER_CASE
                    and cand_metrics["accuracy"] >= champ_metrics["accuracy"] + 0.005
                    and cand_metrics["deal_safety"] >= champ_metrics["deal_safety"]
                    and cand_metrics["retrieval_s"] <= champ_metrics["retrieval_s"] * 1.3)
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "version": f"cycle-{cycle}", "role": "champion" if accepted else "candidate",
                 "accepted": accepted,
                 "stability": round(cand_metrics["accuracy"] - champ_metrics["accuracy"], 4),
                 **cand_metrics}
        history = snapshot(entry)
        print(f"[autoresearch] cycle {cycle}: {json.dumps(entry)}", flush=True)
        if accepted:
            champion, champ_metrics, fails = candidate, cand_metrics, cand_fails
            CHAMPION.write_text(champion)
            print(f"[autoresearch] cycle {cycle}: PROMOTED new champion", flush=True)
        else:
            fails = cand_fails or fails
        time.sleep(CYCLE_SECS)


if __name__ == "__main__":
    main()
