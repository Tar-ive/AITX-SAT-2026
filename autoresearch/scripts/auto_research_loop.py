#!/usr/bin/env python3
"""Continuous autoresearch host wrapper (Karpathy-pattern).

Single-experiment surface (what humans/agents should look at first):
  prepare.py   — frozen eval harness (do not modify)
  train.py     — policy lessons the agent edits
  program.md   — branch → edit → run → keep/discard instructions
  results.tsv  — experiment log

This module is the *always-on* EC2/Railway companion: it loops train-style
mutations, uses the same Pareto gate as prepare.pareto_keep, and POSTs
snapshots to COORDINATOR_URL so Vercel/Railway dashboards stay live.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from difflib import unified_diff
from pathlib import Path

import requests

REPO = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parents[1]))

# Karpathy-root prepare.py is the canonical eval harness.
# Local copies of score/evaluate below remain as fallbacks if prepare is unavailable.
SKILL_SCRIPTS = REPO / "skill" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from evaluate import score_policy, log_result_ml  # noqa: E402
from plan import write_plan, update_experiment, add_experiment  # noqa: E402
from report import generate_report  # noqa: E402
from state import (  # noqa: E402
    init as state_init,
    update_status,
    read_json,
    checkpoint,
    write_control,
)
from usage import track as usage_track  # noqa: E402
from workspace import (  # noqa: E402
    ensure_workspace,
    start_experiment,
    commit_and_merge,
    discard_experiment,
    read_main_file,
)

GOLDEN = json.loads((REPO / "scripts" / "golden_dataset.json").read_text())
SNAPSHOTS = REPO / "data" / "radar_snapshots.json"
RESEARCH_DIR = Path(os.environ.get("AUTORESEARCH_HOME", REPO / "research"))
CHAMPION_LINK = RESEARCH_DIR / "champion-lessons.md"  # stable path for nightly tournament
TARGET_FILE = "champion-lessons.md"
KNOWLEDGE_FILE = "research.md"

CYCLE_SECS = int(os.environ.get("CYCLE_SECS", "300"))
ROLLOUTS_PER_CASE = int(os.environ.get("ROLLOUTS_PER_CASE", "2"))
MODE = os.environ.get("AUTORESEARCH_MODE", "policy").lower()  # policy | knowledge
DEPTH = os.environ.get("AUTORESEARCH_DEPTH", "deep").lower()

DEPTH_TIERS = {
    "quick": {"max_duration": 30, "max_tokens": 500_000, "max_experiments": 10},
    "deep": {"max_duration": 180, "max_tokens": 2_000_000, "max_experiments": 25},
    "unlimited": {"max_duration": 0, "max_tokens": 0, "max_experiments": 30},
}

NVIDIA_KEY = os.environ.get("NVIDIA_INFERENCE_API_KEY") or os.environ.get("NVIDIA_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENCODE_KEY = os.environ.get("OPENCODE_API_KEY", "")
COORD = os.environ.get("COORDINATOR_URL", "").rstrip("/")
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD = os.environ.get("DISCORD_SERVER_ID", "1527850934535717055")
DISCORD_EVAL_CHANNEL = os.environ.get("DISCORD_EVAL_CHANNEL_ID", "")
DISCORD_INSIGHT_EVERY = int(os.environ.get("DISCORD_INSIGHT_EVERY", "5"))

BASE_SYSTEM = """You are a GPU purchase-decision judge for a buying-assistant team.
Given a buyer request, decide where and how to buy. Respond with ONLY a JSON
object: {"recommended_platform": str, "condition": str,
"lead_time_days": int, "reasons": [str, str]}.
Platforms: Amazon (Direct), Amazon Marketplace Third-Party, eBay, Newegg,
Best Buy, Micro Center. Be conservative about warranty and delivery claims."""


def chat(base, key, model, system, user, timeout=90, temperature=0):
    t0 = time.time()
    r = requests.post(
        f"{base}/chat/completions",
        timeout=timeout,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time() - t0


def judge(system, prompt):
    """One rollout with NVIDIA -> OpenRouter fallback. Returns (text, secs)."""
    try:
        return chat(
            "https://integrate.api.nvidia.com/v1",
            NVIDIA_KEY,
            "nvidia/nemotron-3-super-120b-a12b",
            system,
            prompt,
        )
    except Exception:
        if not OPENROUTER_KEY:
            raise
        return chat(
            "https://openrouter.ai/api/v1",
            OPENROUTER_KEY,
            "nvidia/nemotron-3-super-120b-a12b",
            system,
            prompt,
        )


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
    if plat and exp and any(
        p.strip() in plat
        for p in exp.replace(" or ", ",").split(",")
        if p.strip()
    ):
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
    system = BASE_SYSTEM + (
        "\n\nLessons learned from prior graded interactions:\n" + lessons if lessons else ""
    )
    scores, lats, violations, fails = [], [], 0, []
    for case in GOLDEN:
        truth = {
            "expected_platform": case.get("expected_platform", ""),
            **case.get("ground_truth", {}),
        }
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
    return {
        "accuracy": round(sum(scores) / n, 4),
        "retrieval_s": round(sum(lats) / (len(lats) or 1), 2),
        "deal_safety": round(100 - 100 * violations / n, 1),
        "n": len(scores),
    }, fails


def mutate(champion_lessons, history, fails, hypothesis="", evidence_context=None):
    prompt = f"""You are the researcher in an autoresearch loop optimizing a GPU
purchase-decision policy. The policy IS the lessons file below (like
autoresearch's program.md). Objectives: accuracy UP, response length SHORT
(long lessons slow retrieval), zero forbidden-platform picks, no regression.

HYPOTHESIS FOR THIS EXPERIMENT: {hypothesis or '(general improvement)'}

CURRENT CHAMPION LESSONS:
{champion_lessons or '(empty)'}

RECENT SCOREBOARD (newest last): {json.dumps(history[-4:])}

RECALLED USER EVIDENCE AND PRIOR WINNERS:
{json.dumps(evidence_context or {}, ensure_ascii=False)[:5000]}

FAILURES FROM LAST EVALUATION:
{chr(10).join(fails[:12]) or '(none)'}

Write an improved lessons file: <=20 tight bullet rules, generalized from the
failures, no test-case IDs or memorized answers, markdown bullets only.
Reply with ONLY the new lessons file content."""
    sys_msg = "You improve policy instruction files. Output only the file content."
    temperature = 0.4 + 0.5 * ((len(history) % 5) / 4)
    text = None
    if OPENCODE_KEY:
        try:
            text, _ = chat(
                "https://opencode.ai/zen/v1",
                OPENCODE_KEY,
                os.environ.get("RESEARCHER_MODEL", "nemotron-3-ultra-free"),
                sys_msg,
                prompt,
                timeout=240,
                temperature=temperature,
            )
        except Exception:
            text = None
    if text is None:
        if not NVIDIA_KEY and not OPENROUTER_KEY:
            raise RuntimeError("No researcher API key available")
        text, _ = chat(
            "https://integrate.api.nvidia.com/v1",
            NVIDIA_KEY or OPENROUTER_KEY,
            "nvidia/nemotron-3-super-120b-a12b",
            sys_msg,
            prompt,
            timeout=240,
            temperature=temperature,
        )
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


def _sql_quote(value):
    tag = f"q{uuid.uuid4().hex[:10]}"
    return f"${tag}${value or ''}${tag}$"


def _psql(sql):
    password = os.environ.get("SUPABASE_DB_PW", "")
    if not password or not shutil.which("psql"):
        return ""
    dsn = (
        f"host={os.environ.get('SUPABASE_POOLER_HOST', 'aws-0-ca-central-1.pooler.supabase.com')} "
        "port=5432 dbname=postgres "
        f"user={os.environ.get('SUPABASE_POOLER_USER', 'postgres.qzegmkzyzalmakoqxezc')} "
        "sslmode=require"
    )
    result = subprocess.run(
        ["psql", dsn, "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True,
        text=True,
        env={**os.environ, "PGPASSWORD": password},
    )
    if result.returncode:
        print(f"[autoresearch] Supabase skipped: {result.stderr[-220:]}", flush=True)
        return ""
    return result.stdout.strip()


def recall_evidence():
    """Ground mutations in recent user signals and actions that already worked."""
    raw = _psql(
        """
        select json_build_object(
          'episodes', coalesce((
            select json_agg(row_to_json(e)) from (
              select episode_id, channel, request, feedback, quality, lesson
              from public.episodes
              order by inserted_at desc limit 6
            ) e
          ), '[]'::json),
          'prior_winners', coalesce((
            select json_agg(row_to_json(w)) from (
              select action, hypothesis, decision_quality, seconds_per_answer
              from public.harness_experiments where accepted
              order by created_at desc limit 5
            ) w
          ), '[]'::json),
          'latest_soul', (
            select row_to_json(s) from (
              select agent_name, version, diff_lines, summary
              from public.agent_soul_latest where agent_name = 'hermes'
            ) s
          )
        );
        """
    )
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _memory_diff_lines(before, after):
    return sum(
        line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        for line in unified_diff(before.splitlines(), after.splitlines())
    )


def persist_harness_experiment(entry, champion, candidate, evidence, run_id):
    """Write the five metrics and explicit evidence links to Supabase."""
    episode_ids = [
        row["episode_id"] for row in evidence.get("episodes", [])
        if isinstance(row, dict) and row.get("episode_id")
    ]
    preference = next(
        (
            row.get("request") or json.dumps(row.get("feedback") or {})
            for row in evidence.get("episodes", [])
            if isinstance(row, dict) and (row.get("request") or row.get("feedback"))
        ),
        "",
    )
    registry_id = f"{run_id}:{entry['version']}:{entry['ts']}"
    soul = evidence.get("latest_soul") or {}
    policy_diff_lines = _memory_diff_lines(champion, candidate)
    entry["registry_id"] = registry_id
    entry["episodic_diff_lines"] = int(soul.get("diff_lines") or policy_diff_lines)
    entry["knowledge_regression"] = max(0, -float(entry.get("stability") or 0))
    episode_array = "array[" + ",".join(_sql_quote(row) for row in episode_ids) + "]::text[]"
    metadata = json.dumps({
        "provenance": "measured",
        "episodes_tried": len(GOLDEN),
        "rollouts": entry.get("n", 0),
        "stored_samples": 0,
        "version": entry["version"],
        "stability": entry.get("stability", 0),
        "policy_diff_lines": policy_diff_lines,
        "soul_version": soul.get("version"),
        "soul_summary": soul.get("summary"),
    })
    _psql(
        "insert into public.harness_experiments "
        "(experiment_id,action,hypothesis,decision_quality,seconds_per_answer,"
        "forbidden_platform_risk,prompt_injection_risk,memory_diff_lines,"
        "knowledge_regression,accepted,"
        "rolled_back,source_box,evidence_episode_ids,user_preference,test_method,metadata) values ("
        f"{_sql_quote(registry_id)},'mutate_policy',{_sql_quote(entry.get('hypothesis'))},"
        f"{float(entry.get('accuracy') or 0)},{float(entry.get('retrieval_s') or 0)},"
        f"{max(0, 100 - float(entry.get('deal_safety') or 100))},"
        f"null,{entry['episodic_diff_lines']},{entry['knowledge_regression']},"
        f"{'true' if entry.get('accepted') else 'false'},false,'cursor-karpathy',"
        f"{episode_array},{_sql_quote(preference[:500])},"
        f"{_sql_quote('Verifiers frozen golden set + rubric/LLM judge; same cases as champion')},"
        f"{_sql_quote(metadata)}::jsonb) "
        "on conflict (experiment_id) do update set "
        "decision_quality=excluded.decision_quality,seconds_per_answer=excluded.seconds_per_answer,"
        "forbidden_platform_risk=excluded.forbidden_platform_risk,"
        "prompt_injection_risk=excluded.prompt_injection_risk,"
        "memory_diff_lines=excluded.memory_diff_lines,"
        "knowledge_regression=excluded.knowledge_regression,accepted=excluded.accepted,"
        "evidence_episode_ids=excluded.evidence_episode_ids,user_preference=excluded.user_preference,"
        "test_method=excluded.test_method,metadata=excluded.metadata;"
    )


def snapshot(entry):
    hist = json.loads(SNAPSHOTS.read_text()) if SNAPSHOTS.exists() else []
    hist.append(entry)
    SNAPSHOTS.parent.mkdir(exist_ok=True)
    SNAPSHOTS.write_text(json.dumps(hist, indent=1))
    if COORD:
        for path in ("/api/radar", "/api/evaluations"):
            try:
                requests.post(
                    f"{COORD}{path}",
                    timeout=15,
                    json={"source": "autoresearch-loop", **entry},
                )
            except requests.RequestException:
                pass
    post_discord_insight(entry, hist)
    return hist


def post_discord_insight(entry, history):
    """Post promotions and periodic measured checkpoints; no webhook required."""
    if not DISCORD_TOKEN or "accepted" not in entry:
        return
    number = int(re.search(r"\d+", entry.get("version", "0")).group()) if re.search(
        r"\d+", entry.get("version", "")
    ) else len(history)
    if not entry.get("accepted") and number % DISCORD_INSIGHT_EVERY:
        return
    champions = [row for row in history if row.get("role") == "champion"]
    baseline = champions[0] if champions else history[0]
    delta = float(entry.get("accuracy", 0)) - float(baseline.get("accuracy", 0))
    verdict = "PROMOTED" if entry.get("accepted") else "checkpoint"
    content = (
        f"🔬 **AutoResearch {verdict} · {entry.get('version')}**\n"
        f"Decision quality **{entry.get('accuracy', 0):.4f}** ({delta:+.4f}) · "
        f"seconds/answer **{entry.get('retrieval_s', 0):.2f}s**\n"
        "Prompt injection risk **not measured** · "
        f"memory diff **{entry.get('episodic_diff_lines', 0)} lines** · "
        f"knowledge regression **{entry.get('knowledge_regression', 0):.4f}**\n"
        f"Hypothesis: {entry.get('hypothesis') or 'baseline policy check'}"
    )
    try:
        headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}
        rows = requests.get(
            f"https://discord.com/api/v10/guilds/{DISCORD_GUILD}/channels",
            headers=headers,
            timeout=15,
        ).json()
        target = next(
            (row for row in rows if row.get("id") == DISCORD_EVAL_CHANNEL),
            next(
                (row for row in rows if row.get("name") == "eval"),
                next((row for row in rows if row.get("name") == "daily"), None),
            ),
        )
        if not target:
            return
        if target.get("type") == 15:
            response = requests.post(
                f"https://discord.com/api/v10/channels/{target['id']}/threads",
                headers=headers,
                json={
                    "name": f"RSI eval — {entry.get('version', 'experiment')}"[:90],
                    "message": {"content": content[:1900]},
                },
                timeout=15,
            )
        else:
            response = requests.post(
                f"https://discord.com/api/v10/channels/{target['id']}/messages",
                headers=headers,
                json={"content": content[:1900]},
                timeout=15,
            )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"[autoresearch] Discord insight skipped: {error}", flush=True)


def _tier_limits():
    tier = DEPTH_TIERS.get(DEPTH, DEPTH_TIERS["deep"])
    return {
        "max_duration": int(os.environ.get("MAX_DURATION_MINUTES", tier["max_duration"])),
        "max_tokens": int(os.environ.get("MAX_TOKENS", tier["max_tokens"])),
        "max_experiments": int(os.environ.get("MAX_EXPERIMENTS", tier["max_experiments"])),
    }


def _default_policy_plan(max_exp):
    """Seed experiment hypotheses for the policy mutation loop."""
    ideas = [
        ("investigate", "Tighten warranty/seller-filter rules from recent fails"),
        ("investigate", "Add counterfeit / too-good-to-be-true price heuristics"),
        ("deepen", "Compress lessons: drop redundant bullets, keep signal"),
        ("investigate", "Clarify platform priority for sealed vs used GPUs"),
        ("verify", "Re-check lead-time conservatism without hurting accuracy"),
        ("synthesize", "Merge overlapping rules into fewer generalized bullets"),
        ("deepen", "Strengthen Micro Center / local-pickup guidance"),
        ("investigate", "Tax/refund and marketplace fee awareness rules"),
        ("verify", "Ensure no test-case memorization leaked into lessons"),
        ("synthesize", "Final pass: <=15 bullets, max clarity"),
    ]
    experiments = []
    for i in range(min(max_exp, len(ideas) * 3)):
        typ, hyp = ideas[i % len(ideas)]
        experiments.append({
            "id": i + 1,
            "type": typ,
            "hypothesis": hyp if i < len(ideas) else f"{hyp} (pass {i // len(ideas) + 1})",
            "target_section": TARGET_FILE,
            "status": "pending",
        })
    return experiments


def _sync_champion_link(workspace_dir):
    """Keep research/champion-lessons.md in sync for nightly_master_cycle."""
    content = read_main_file(workspace_dir, TARGET_FILE)
    CHAMPION_LINK.parent.mkdir(parents=True, exist_ok=True)
    CHAMPION_LINK.write_text(content)
    return content


def _read_control(run_dir):
    return read_json(os.path.join(run_dir, "control.json"))


def _budget_exceeded(run_dir):
    """Call check_budget and parse whether limits are hit (no stdout dependency)."""
    cfg = read_json(os.path.join(run_dir, "config.json"))
    st = read_json(os.path.join(run_dir, "status.json"))
    usage = read_json(os.path.join(run_dir, "usage.json"))
    md, mt = cfg.get("max_duration_minutes", 180), cfg.get("max_tokens", 2_000_000)
    cap = cfg.get("max_experiments_hard_cap", 30)
    done = st.get("experiments_done", 0)
    tokens = usage.get("total_tokens", 0)
    violations = []
    if md and cfg.get("created"):
        try:
            from datetime import datetime, timezone
            elapsed = (
                datetime.now(timezone.utc) - datetime.fromisoformat(cfg["created"])
            ).total_seconds() / 60
            if elapsed > md:
                violations.append(f"time_exceeded: {elapsed:.0f}min > {md}min")
        except Exception:
            pass
    if mt and tokens > mt:
        violations.append(f"tokens_exceeded: {tokens} > {mt}")
    if done >= cap:
        violations.append(f"experiments_exceeded: {done} >= {cap}")
    return bool(violations), violations


def _finish(run_dir, phase="completed"):
    update_status(run_dir, phase)
    # Silence generate_report's print by capturing via redirect is unnecessary;
    # it prints JSON which is fine for logs.
    try:
        generate_report(run_dir)
    except Exception as e:
        print(f"[autoresearch] report generation failed: {e}", flush=True)
    report = Path(run_dir) / "report.md"
    if report.exists():
        print(f"[autoresearch] report → {report}", flush=True)


def setup_run(goal=None):
    limits = _tier_limits()
    rid = os.environ.get("RUN_ID") or f"policy_{time.strftime('%Y%m%d')}_{os.getpid()}"
    run_dir = str(RESEARCH_DIR / "runs" / rid)
    goal = goal or (
        "Optimize GPU purchase-decision policy lessons for accuracy, "
        "deal safety, and retrieval speed on the frozen golden dataset"
    )
    # state_init prints JSON; that's ok
    state_init(
        run_dir,
        goal,
        "policy" if MODE == "policy" else "knowledge",
        "gpu-deal-judge",
        DEPTH,
        limits["max_experiments"],
        limits["max_duration"],
        limits["max_tokens"],
    )
    seed = ""
    if CHAMPION_LINK.exists():
        seed = CHAMPION_LINK.read_text()
    elif (REPO / "data" / "lessons.md").exists():
        seed = (REPO / "data" / "lessons.md").read_text()

    if MODE == "knowledge":
        initial = {
            KNOWLEDGE_FILE: (
                "# GPU Market Research\n\n"
                "## Overview\n\n## Platforms\n\n## Pricing\n\n"
                "## Risks\n\n## Recommendations\n"
            )
        }
        target = KNOWLEDGE_FILE
    else:
        initial = {TARGET_FILE: seed or "# Champion lessons\n\n(empty baseline)\n"}
        target = TARGET_FILE

    ws = ensure_workspace(os.path.join(run_dir, "workspace"), initial_files=initial)
    write_plan(run_dir, json.dumps(_default_policy_plan(limits["max_experiments"])))
    update_status(
        run_dir,
        "executing",
        experiments_total=limits["max_experiments"],
        current_experiment=None,
    )
    if MODE == "policy":
        _sync_champion_link(ws)
    # Register for multi-run tracking
    try:
        sys.path.insert(0, str(SKILL_SCRIPTS))
        from registry import register
        register(rid, "aitx", "local", "0", goal, f"loop-{rid}")
    except Exception as e:
        print(f"[autoresearch] registry skip: {e}", flush=True)
    return run_dir, ws, target, rid


def policy_cycle(run_dir, workspace_dir, exp, history, champ_metrics, fails):
    """One branch → mutate → evaluate → merge/revert cycle."""
    exp_id = exp["id"]
    desc = re.sub(r"[^a-zA-Z0-9_-]+", "-", exp.get("hypothesis", "mutate")[:40]).strip("-") or "mutate"
    update_experiment(run_dir, exp_id, "in_progress")
    start_experiment(workspace_dir, exp_id, desc)

    champion = read_main_file(workspace_dir, TARGET_FILE)
    evidence = recall_evidence()
    try:
        candidate = mutate(
            champion,
            history,
            fails,
            hypothesis=exp.get("hypothesis", ""),
            evidence_context=evidence,
        )
    except Exception as e:
        discard_experiment(workspace_dir, exp_id, desc)
        update_experiment(run_dir, exp_id, "failed", reason=str(e))
        return None, champ_metrics, fails, False

    # Write candidate onto the experiment branch
    (Path(workspace_dir) / TARGET_FILE).write_text(candidate)
    cand_metrics, cand_fails = evaluate(candidate)
    min_cases = max(1, int(0.6 * len(GOLDEN) * ROLLOUTS_PER_CASE))
    decision = score_policy(cand_metrics, champ_metrics, min_cases=min_cases)
    accepted = decision["decision"] == "MERGE"

    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": f"exp-{exp_id}",
        "role": "champion" if accepted else "candidate",
        "accepted": accepted,
        "stability": decision["stability"],
        "hypothesis": exp.get("hypothesis", ""),
        **cand_metrics,
    }
    persist_harness_experiment(
        entry,
        champion,
        candidate,
        evidence,
        Path(run_dir).name,
    )
    history = snapshot(entry)
    print(f"[autoresearch] exp {exp_id}: {json.dumps(entry)}", flush=True)

    if accepted:
        commit_and_merge(
            workspace_dir, exp_id, desc,
            f"exp {exp_id}: {exp.get('hypothesis', 'improve')[:60]}",
        )
        update_experiment(run_dir, exp_id, "merged", reason=decision["reason"])
        log_result_ml(
            run_dir, exp_id, desc, "accuracy",
            cand_metrics["accuracy"], champ_metrics["accuracy"],
            "MERGE", decision["reason"],
        )
        _sync_champion_link(workspace_dir)
        print(f"[autoresearch] exp {exp_id}: MERGED new champion", flush=True)
        return history, cand_metrics, cand_fails, True

    discard_experiment(workspace_dir, exp_id, desc)
    update_experiment(run_dir, exp_id, "reverted", reason=decision["reason"])
    log_result_ml(
        run_dir, exp_id, desc, "accuracy",
        cand_metrics["accuracy"], champ_metrics["accuracy"],
        "REVERT", decision["reason"],
    )
    return history, champ_metrics, cand_fails or fails, False




# --- Karpathy prepare.py override (canonical metric) ---
try:
    import importlib.util as _ilu
    _prep_path = REPO / "prepare.py"
    if _prep_path.exists():
        _spec = _ilu.spec_from_file_location("aitx_prepare", _prep_path)
        _prep = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_prep)
        evaluate = _prep.evaluate  # noqa: F811 — prefer frozen harness
        print("[autoresearch] using prepare.py evaluate() as ground truth", flush=True)
except Exception as _e:
    pass

def resync_coordinator():
    """Replace Railway history from durable EC2 state after an ephemeral wipe."""
    if not COORD or not SNAPSHOTS.exists():
        return
    try:
        hist = json.loads(SNAPSHOTS.read_text())
        response = requests.post(
            f"{COORD}/api/radar",
            timeout=20,
            json={
                "replace": True,
                "rows": [{"source": "autoresearch-loop", **e} for e in hist],
            },
        )
        response.raise_for_status()
        print(f"[autoresearch] resynced {len(hist)} snapshots to coordinator", flush=True)
    except (requests.RequestException, json.JSONDecodeError, OSError):
        pass


def main():
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    resync_coordinator()
    run_dir, workspace_dir, target, rid = setup_run()
    print(f"[autoresearch] run_id={rid} mode={MODE} depth={DEPTH} dir={run_dir}", flush=True)

    champion = read_main_file(workspace_dir, TARGET_FILE) if MODE == "policy" else ""
    print("[autoresearch] evaluating champion baseline...", flush=True)
    if MODE == "policy":
        champ_metrics, fails = evaluate(champion)
    else:
        # Knowledge mode baseline: empty metrics placeholder; agent rubric later
        champ_metrics, fails = {"accuracy": 0, "retrieval_s": 0, "deal_safety": 100, "n": 0}, []
    history = snapshot({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "champion-0",
        "role": "champion",
        "run_id": rid,
        **champ_metrics,
    })

    consecutive_failures = 0
    merged = reverted = failed = 0
    done = 0

    while True:
        ctrl = _read_control(run_dir)
        action = (ctrl.get("action") or "none").lower()
        if action == "pause":
            print("[autoresearch] paused via control.json", flush=True)
            update_status(run_dir, "paused")
            checkpoint(run_dir, done, done + 1)
            time.sleep(CYCLE_SECS)
            continue
        if action == "stop":
            print("[autoresearch] stop via control.json", flush=True)
            _finish(run_dir, "stopped")
            write_control(run_dir, "none")
            break
        if action == "adjust" and ctrl.get("addendum"):
            add_experiment(run_dir, "deepen", ctrl["addendum"], target)
            write_control(run_dir, "none")

        exceeded, violations = _budget_exceeded(run_dir)
        if exceeded:
            print(f"[autoresearch] budget exceeded: {violations}", flush=True)
            _finish(run_dir, "budget_exceeded")
            break

        # next pending experiment
        plan = read_json(os.path.join(run_dir, "plan.json"))
        pending = next(
            (e for e in plan.get("experiments", []) if e.get("status") == "pending"),
            None,
        )
        if pending is None:
            print("[autoresearch] all planned experiments done", flush=True)
            _finish(run_dir, "completed")
            break

        print(
            f"[autoresearch] exp {pending['id']}: {pending.get('hypothesis', '')}",
            flush=True,
        )
        try:
            if MODE == "policy":
                history, champ_metrics, fails, ok = policy_cycle(
                    run_dir, workspace_dir, pending, history, champ_metrics, fails,
                )
                if history is None:
                    consecutive_failures += 1
                    failed += 1
                elif ok:
                    consecutive_failures = 0
                    merged += 1
                else:
                    consecutive_failures = 0
                    reverted += 1
            else:
                # Knowledge mode: mutate research.md via researcher, score with rubric
                # (lightweight self-eval when no browser tools available in this loop)
                print(
                    "[autoresearch] knowledge mode requires agent tooling; "
                    "use skills/autoresearch templates for full Mode 2. Stopping.",
                    flush=True,
                )
                _finish(run_dir, "completed")
                break
        except Exception as e:
            print(f"[autoresearch] cycle error: {e}; continuing", flush=True)
            consecutive_failures += 1
            failed += 1
            try:
                discard_experiment(
                    workspace_dir, pending["id"],
                    re.sub(r"[^a-zA-Z0-9_-]+", "-", pending.get("hypothesis", "x")[:40]).strip("-") or "x",
                )
            except Exception:
                pass
            update_experiment(run_dir, pending["id"], "failed", reason=str(e))

        done += 1
        if done % 5 == 0:
            resync_coordinator()
        update_status(
            run_dir,
            "executing",
            experiments_done=done,
            experiments_merged=merged,
            experiments_reverted=reverted,
            experiments_failed=failed,
            current_experiment=pending["id"],
        )
        checkpoint(run_dir, done, done + 1)
        # Rough token tracking (researcher + eval rollouts); exact when usage.py wired
        try:
            usage_track(run_dir, pending["id"], 2000, 800)
        except Exception:
            pass

        if consecutive_failures >= 3:
            print("[autoresearch] 3 consecutive failures → auto-pause", flush=True)
            update_status(run_dir, "paused_error")
            write_control(run_dir, "pause", addendum="auto-pause after 3 failures")
            checkpoint(run_dir, done, done + 1)
            consecutive_failures = 0

        # Mid-run replan every 5 experiments if under hard cap
        if done % 5 == 0:
            cfg = read_json(os.path.join(run_dir, "config.json"))
            cap = cfg.get("max_experiments_hard_cap", 30)
            if done < cap:
                add_experiment(
                    run_dir, "deepen",
                    f"Replan pass after {done} experiments: target remaining fails",
                    target,
                )

        time.sleep(CYCLE_SECS)


if __name__ == "__main__":
    main()
