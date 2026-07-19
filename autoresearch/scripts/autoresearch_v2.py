#!/usr/bin/env python3
"""Autoresearch v2 — fixes the three diagnosed faults of v1:

  1. STUCK (0 promotions): v1 froze a lucky-high champion, then eval noise
     (±0.04, n=19-30) swamped the 0.005 bar so nothing could beat it.
     FIX: PAIRED evaluation — re-score the champion AND the candidate on the
     SAME golden cases every round, so measurement noise cancels; promote on a
     paired win with a real margin.

  2. ISOLATED from Supabase: v1 never read the seed ideas or wrote promotions.
     FIX: seed the researcher from public.harness_experiments (what worked),
     and write every verdict to harness_experiments + promotions to agent_soul.

  3. EXPLORATION vs SAFETY: research agents should try interesting things
     (hub-search, component-swap, distill) without being blocked — only
     genuinely dangerous actions are caught. FIX: the triage boundary below.

Triage — what the harness may do freely vs what OpenShell/HiddenLayer catch:
  EXPLORE FREELY (allowlisted egress: nvidia, openrouter, opencode, github,
    supabase, verifiers hub): mutate policy, search hub, read docs, propose
    component swaps, distill. None of this is blocked.
  CAUGHT (OpenShell DENIES + logged, HiddenLayer flags): egress to any host
    NOT on the research allowlist (exfiltration), a mutation whose text carries
    a prompt-injection (HiddenLayer signal on the candidate policy), or any
    attempt to touch credentials / change its own OpenShell policy. These are
    surfaced to #eval for human triage, never silently swallowed — the agent
    stays curious, but can't cross a security boundary unnoticed.

Env: NVIDIA_INFERENCE_API_KEY (+OPENROUTER), OPENCODE_API_KEY, SUPABASE_DB_PW
(+pooler), optional COORDINATOR_URL, HIDDENLAYER_CLIENT_ID/SECRET, CYCLE_SECS.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests

REPO = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parents[2]))


def _find_golden():
    for p in [REPO / "scripts" / "golden_dataset.json",
              REPO / "autoresearch" / "scripts" / "golden_dataset.json",
              REPO / "backend" / "scripts" / "golden_dataset.json",
              Path(__file__).with_name("golden_dataset.json")]:
        if p.exists():
            return p
    raise FileNotFoundError("golden_dataset.json not found")


GOLDEN = json.loads(_find_golden().read_text())
CYCLE_SECS = int(os.environ.get("CYCLE_SECS", "300"))
ROLLOUTS = int(os.environ.get("ROLLOUTS_PER_CASE", "3"))
NVIDIA = os.environ.get("NVIDIA_INFERENCE_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
OPENROUTER = os.environ.get("OPENROUTER_API_KEY", "")
OPENCODE = os.environ.get("OPENCODE_API_KEY", "")
COORD = os.environ.get("COORDINATOR_URL", "").rstrip("/")
BOUNDARIES = json.loads(
    (REPO / "autoresearch" / "improvement-boundaries.json").read_text()
)


def envq(n, d=""):
    return os.environ.get(n, d).strip().strip("'").strip('"')


DSN = (f"host={envq('SUPABASE_POOLER_HOST','aws-0-ca-central-1.pooler.supabase.com')} "
       f"port=5432 dbname=postgres user={envq('SUPABASE_POOLER_USER','postgres.qzegmkzyzalmakoqxezc')} "
       f"sslmode=require")


def psql(sql, out=True):
    r = subprocess.run(["psql", DSN, "-t", "-A", "-c", sql], capture_output=True, text=True,
                       env={**os.environ, "PGPASSWORD": envq("SUPABASE_DB_PW")})
    return r.stdout.strip() if out else r.returncode


def git_ref():
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except subprocess.SubprocessError:
        return ""


BASE_SYSTEM = ("You are a GPU purchase-decision judge. Given a buyer request, output ONLY "
               'a JSON object {"recommended_platform": str, "condition": str, "lead_time_days": int}. '
               "Be conservative about warranty and delivery.")


def chat(base, key, model, system, user, temp=0):
    r = requests.post(f"{base}/chat/completions", timeout=90,
                      headers={"Authorization": f"Bearer {key}"},
                      json={"model": model, "temperature": temp,
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def judge(system, prompt):
    for base, key in [("https://integrate.api.nvidia.com/v1", NVIDIA),
                      ("https://openrouter.ai/api/v1", OPENROUTER)]:
        if not key:
            continue
        try:
            return chat(base, key, "nvidia/nemotron-3-super-120b-a12b", system, prompt)
        except requests.RequestException:
            continue
    raise RuntimeError("both inference providers failed")


def score_one(text, truth):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        pred = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        pred = None
    if not pred:
        return 0.0
    s = 0.0
    plat = str(pred.get("recommended_platform", "")).lower()
    avoid = [a.lower() for a in truth.get("avoid_platforms", [])]
    if plat and not any(a in plat or plat in a for a in avoid):
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
    return round(s, 3)


def evaluate(lessons, cases):
    """Evaluate a policy on a FIXED set of cases (paired, noise-cancelling).
    Also times each rollout so seconds_per_answer is measured, not guessed."""
    system = BASE_SYSTEM + ("\n\nLessons:\n" + lessons if lessons else "")
    scores, secs = [], []
    for c in cases:
        truth = {"expected_platform": c.get("expected_platform", ""), **c.get("ground_truth", {})}
        try:
            t0 = time.time()
            out = judge(system, c["prompt"])
            secs.append(time.time() - t0)
            scores.append(score_one(out, truth))
        except RuntimeError:
            pass
    mean = (sum(scores) / len(scores)) if scores else 0.0
    sec = round(sum(secs) / len(secs), 2) if secs else 0.0
    return mean, len(scores), sec


def injection_risk():
    """Run the combined defense-in-depth injection eval; return the % risk.
    Expensive, so called only on promotion. Falls back to None on error."""
    script = REPO / "autoresearch" / "scripts" / "injection_combined_eval.py"
    if not (script.exists() and os.environ.get("HIDDENLAYER_CLIENT_ID")):
        return None
    try:
        r = subprocess.run(["python3", str(script)], capture_output=True, text=True, timeout=240)
        for line in r.stdout.splitlines():
            if line.startswith("{"):
                return json.loads(line).get("risk_pct")
    except (subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return None


def seed_hypotheses():
    """Read what worked from Supabase as the researcher's idea seed."""
    rows = psql("select hypothesis from public.harness_experiments where accepted "
                "and hypothesis is not null order by created_at desc limit 12;")
    return [h for h in rows.splitlines() if h.strip()]


def champion_injection_risk():
    raw = psql(
        "select prompt_injection_risk from public.harness_experiments "
        "where accepted and prompt_injection_risk is not null "
        "order by created_at desc limit 1;"
    )
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def mutate(champion, seeds, cycle):
    prompt = (f"Improve this GPU purchase-decision policy. It is scored on decision quality, "
              f"speed, injection resistance, and no regression.\n\nCURRENT:\n{champion or '(empty)'}\n\n"
              f"WHAT HAS WORKED BEFORE (seed ideas from the registry):\n" + "\n".join(f"- {s}" for s in seeds[:8]) +
              f"\n\nWrite an improved policy: <=18 tight bullet rules, generalized, markdown only. "
              f"Try a different angle than the current one. Output only the rules.")
    sysmsg = "You improve policy files. Output only the file content."
    try:
        t = chat("https://opencode.ai/zen/v1", OPENCODE, "nemotron-3-ultra-free", sysmsg, prompt, temp=0.6)
    except requests.RequestException:
        t = judge(sysmsg, prompt)
    return re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL).strip()


def record(exp_id, action, hyp, dq, sec, inj, mem, reg, accepted, *,
           episodes, rollouts, champion_score, margin, source="autoresearch-v2"):
    """Record all FIVE metrics: decision_quality, seconds_per_answer,
    prompt_injection_risk, memory_diff_lines, knowledge_regression."""
    def lit(s):
        return "$v$" + str(s).replace("$", "") + "$v$"
    injv = "null" if inj is None else inj
    metadata = json.dumps({
        "provenance": "paired-live-eval",
        "episodes_tried": episodes,
        "rollouts": rollouts,
        "champion_score": champion_score,
        "paired_margin": margin,
        "git_hash": git_ref(),
    })
    psql(f"insert into public.harness_experiments (experiment_id,action,hypothesis,"
         f"decision_quality,seconds_per_answer,forbidden_platform_risk,prompt_injection_risk,"
         f"memory_diff_lines,knowledge_regression,accepted,source_box,metadata) values "
         f"({lit(exp_id)},{lit(action)},{lit(hyp)},{dq},{sec},{injv if injv!='null' else 0},{injv},"
         f"{mem},{reg},{str(accepted).lower()},{lit(source)},{lit(metadata)}::jsonb) "
         f"on conflict (experiment_id) do nothing;",
         out=False)
    if COORD:
        try:
            requests.post(f"{COORD}/api/radar", timeout=12, json={
                "source": "autoresearch-v2", "version": exp_id, "accuracy": dq,
                "role": "champion" if accepted else "candidate", "retrieval_s": sec,
                "deal_safety": 100 - (injv if injv != "null" else 0), "memory_diff_lines": mem})
        except requests.RequestException:
            pass


def main():
    research = REPO / "research"
    research.mkdir(exist_ok=True)
    champ_file = research / "champion-lessons.md"
    champion = champ_file.read_text() if champ_file.exists() else ""
    seeds = seed_hypotheses()
    print(f"[v2] seeded {len(seeds)} hypotheses from Supabase; champion {'loaded' if champion else 'empty'}",
          flush=True)
    # champ_best = the highest score the champion has actually ACHIEVED, not a
    # noisy re-measurement. Promotion must clear this ceiling so the champion
    # can only ratchet UP — fixes the downward-drift bug (a candidate beating a
    # noisy-low champion re-eval could otherwise regress absolute accuracy).
    champ_best, _, _ = evaluate(champion, GOLDEN) if champion else (0.0, 0, 0.0)
    print(f"[v2] champion best-established score: {champ_best:.3f}", flush=True)
    cycle = 0
    while True:
        cycle += 1
        cand = mutate(champion, seeds, cycle)
        # PAIRED eval: same cases, both policies, this round — noise cancels.
        cand_dq, nc, cand_sec = evaluate(cand, GOLDEN)
        champ_dq, nch, champ_sec = evaluate(champion, GOLDEN)
        margin = round(cand_dq - champ_dq, 4)
        # Promote only if BOTH: (a) genuinely better THIS round (paired, noise-
        # cancelled) AND (b) not below the champion's best-established score.
        quality_ok = margin >= 0.01
        no_regression = cand_dq >= champ_best - 0.005
        coverage_ok = nc >= 0.8 * len(GOLDEN)
        latency_ok = not champ_sec or cand_sec <= 1.3 * champ_sec
        exp_id = f"v2-c{cycle}-{int(cand_dq*1000)}"
        # The expensive injection scan runs only after the paired quality,
        # coverage, and latency gates pass, but before promotion is committed.
        inj = mem = None
        reg = round(abs(min(0.0, margin)), 4)  # positive regression magnitude
        if quality_ok and coverage_ok and latency_ok and reg == 0:
            inj = injection_risk()
        prior_inj = champion_injection_risk()
        injection_limit = BOUNDARIES["metrics"]["prompt_injection_risk"]["hard_ceiling"]
        injection_ok = (
            inj is not None
            and inj <= injection_limit
            and (prior_inj is None or inj <= prior_inj)
        )
        accepted = quality_ok and no_regression and coverage_ok and latency_ok and reg == 0 and injection_ok
        if accepted:
            champion = cand
            champ_best = max(champ_best, cand_dq)  # ratchet the ceiling UP only
            champ_file.write_text(champion)
            rec = REPO / "autoresearch" / "scripts" / "promote_to_soul.py"
            if rec.exists():
                p = subprocess.run(["python3", str(rec), "--agent", "hermes", "--lessons",
                                    str(champ_file), "--experiment", exp_id,
                                    "--git-ref", git_ref()], capture_output=True, text=True)
                m = re.search(r"merged (\d+) new", p.stdout)
                mem = int(m.group(1)) if m else 0
        record(exp_id, "mutate_policy", (cand.splitlines() or ["(empty)"])[0][:120],
               cand_dq, cand_sec, inj, mem or 0, reg, accepted,
               episodes=len(GOLDEN), rollouts=nc, champion_score=champ_dq, margin=margin)
        why = "" if accepted else (" (below best)" if quality_ok and not no_regression else "")
        print(f"[v2] cycle {cycle}: cand={cand_dq:.3f} champ={champ_dq:.3f} best={champ_best:.3f} "
              f"margin={margin:+.3f} {cand_sec:.1f}s/ans -> {'PROMOTE' if accepted else 'reject'}{why}", flush=True)
        if quality_ok and not accepted:
            print(
                f"[v2] gate: coverage={coverage_ok} latency={latency_ok} "
                f"injection={inj if inj is not None else 'unmeasured'} "
                f"(champion={prior_inj if prior_inj is not None else 'none'})",
                flush=True,
            )
        if accepted:
            print(f"[v2] cycle {cycle}: PROMOTED (+{margin:.3f}) — SOUL +{mem} lines, "
                  f"injection_risk={inj}% — posting #eval", flush=True)
            digest = REPO / "autoresearch" / "scripts" / "post_eval_digest.py"
            if digest.exists():
                subprocess.run(["python3", str(digest)], capture_output=True,
                               env={**os.environ, "REPO_DIR": str(REPO)})
            seeds = seed_hypotheses()
        time.sleep(CYCLE_SECS)


if __name__ == "__main__":
    main()
