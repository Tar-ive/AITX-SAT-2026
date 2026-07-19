#!/usr/bin/env python3
"""Read-only dashboard API backed by the hosted Supabase project."""

import csv
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from decimal import Decimal
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "autoresearch/scripts"))

from prepare_rsi_story import build_story  # noqa: E402

PORT = int(os.getenv("DASHBOARD_API_PORT", "8787"))
RSI_RUNS_CSV = Path(os.getenv("RSI_RUNS_CSV", ROOT / "autoresearch/data/rsi_runs.csv"))
MODEL_METRICS_CSV = Path(os.getenv("MODEL_METRICS_CSV", ROOT / "autoresearch/data/model_metrics.csv"))
LATEST_RSI_EVAL_JSON = Path(os.getenv("LATEST_RSI_EVAL_JSON", ROOT / "autoresearch/data/latest_rsi_eval.json"))
LESSONS_FILE = Path(os.getenv("RSI_LESSONS_FILE", ROOT / "autoresearch/data/lessons.md"))
RADAR_SNAPSHOTS = Path(os.getenv("RADAR_SNAPSHOTS", ROOT / "autoresearch/data/radar_snapshots.json"))
COORDINATOR_URL = os.getenv(
    "COORDINATOR_URL",
    "https://nemoclaw-coordinator-api-production.up.railway.app",
).rstrip("/")
VERIFIERS_EVAL_DIR = ROOT / "autoresearch/environments/gpu_deal_judge/outputs/evals"
DISCORD_RSI_CHANNEL_ID = os.getenv("DISCORD_RSI_CHANNEL_ID", "1527922756480401478")
CATEGORIES = {
    "macbook": re.compile(r"\bmacbook\b", re.I),
    "gpu": re.compile(r"\b(gpu|graphics card|geforce|rtx|gtx|radeon)\b", re.I),
    "ram": re.compile(r"\b(ddr[345]|sodimm|so-dimm|dimm|desktop memory)\b", re.I),
}
IMPROVEMENT_RUNS = [
    {"version": "v1.4", "label": "Refine pricing & URLs", "current": True, "decision_quality": .763, "decision_ci": .018, "landed_price_error": 7.6, "landed_ci": .7, "latency": 2.31, "latency_ci": .27, "valid_url_rate": 96.2, "url_ci": 1.3, "unsupported_claims": .72, "claims_ci": .18, "forecast_regret": 56, "regret_ci": 9},
    {"version": "v1.3", "label": "Stricter evidence + judge", "decision_quality": .734, "decision_ci": .019, "landed_price_error": 8.4, "landed_ci": .8, "latency": 2.12, "latency_ci": .25, "valid_url_rate": 95.0, "url_ci": 1.4, "unsupported_claims": .90, "claims_ci": .20, "forecast_regret": 63, "regret_ci": 10},
    {"version": "v1.2", "label": "Better retrieval mix", "decision_quality": .701, "decision_ci": .020, "landed_price_error": 9.6, "landed_ci": .9, "latency": 1.98, "latency_ci": .24, "valid_url_rate": 93.5, "url_ci": 1.6, "unsupported_claims": 1.18, "claims_ci": .26, "forecast_regret": 72, "regret_ci": 11},
    {"version": "v1.1", "label": "Initial harness", "baseline": True, "decision_quality": .642, "decision_ci": .022, "landed_price_error": 11.3, "landed_ci": 1.0, "latency": 1.75, "latency_ci": .22, "valid_url_rate": 91.2, "url_ci": 1.7, "unsupported_claims": 1.73, "claims_ci": .30, "forecast_regret": 93, "regret_ci": 13},
]


def load_env():
    env_file = Path(os.getenv("AITX_ENV_FILE", ROOT / ".env"))
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def database():
    """Use the linked hosted pooler because the direct Supabase host is IPv6-only here."""
    if database_url := os.getenv("DATABASE_URL"):
        return psycopg2.connect(database_url, sslmode="require", connect_timeout=8)
    pooler = os.getenv("SUPABASE_POOLER_URL")
    if pooler:
        endpoint = pooler.rsplit("@", 1)[-1].split("/", 1)[0]
        host, port = endpoint.rsplit(":", 1)
    else:
        host = os.getenv("SUPABASE_POOLER_HOST", "aws-0-ca-central-1.pooler.supabase.com")
        port = os.getenv("SUPABASE_POOLER_PORT", "5432")
    project_ref = os.getenv("SUPABASE_PROJECT_REF", "qzegmkzyzalmakoqxezc")
    return psycopg2.connect(
        host=host,
        port=int(port),
        user=f"postgres.{project_ref}",
        password=os.environ["SUPABASE_DB_PW"],
        dbname="postgres",
        sslmode="require",
        connect_timeout=8,
    )


def category_for(title):
    return next((name for name, pattern in CATEGORIES.items() if pattern.search(title)), None)


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def marketplace(category):
    with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            select l.id, s.slug as source, s.name as source_name, l.title, l.condition,
                   l.seller_name, l.seller_rating, l.item_price, l.shipping_price,
                   l.total_price, l.currency, l.listing_url, l.image_url, l.availability,
                   l.collection_method, l.collector, l.last_seen_at
            from public.listings l
            join public.sources s on s.id = l.source_id
            where l.collector not ilike '%%sandbox%%'
            order by l.total_price asc, l.last_seen_at desc
            """
        )
        rows = []
        for row in cursor.fetchall():
            row = {key: json_value(value) for key, value in row.items()}
            row["category"] = category_for(row["title"])
            if row["category"] and (category == "all" or row["category"] == category):
                rows.append(row)

        cursor.execute(
            """
            select max(r.finished_at) as last_synced_at,
                   count(*) filter (where r.status = 'succeeded') as successful_syncs
            from public.sync_runs r
            join public.sources s on s.id = r.source_id
            where s.enabled = true
            """
        )
        sync = {key: json_value(value) for key, value in cursor.fetchone().items()}

    sources = sorted({row["source_name"] for row in rows})
    return {
        "data_status": "live",
        "database": "hosted Supabase",
        "category": category,
        "listings": rows,
        "meta": {
            **sync,
            "listing_count": len(rows),
            "source_count": len(sources),
            "sources": sources,
            "sandbox_excluded": True,
        },
    }


def rsi_operations():
    fields = {
        "Model": "model",
        "Memory Tools": "memory_tools",
        "Messages": "messages",
        "Memory Keys": "memory_keys",
        "Reflection (k chars)": "reflection_k_chars",
        "Response (k chars)": "response_k_chars",
        "Memory Write (k chars)": "memory_write_k_chars",
    }
    with MODEL_METRICS_CSV.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = set(fields) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"model metrics missing: {', '.join(sorted(missing))}")
        metrics = [
            {
                key: row[column] if key == "model" else float(row[column])
                for column, key in fields.items()
            }
            for row in reader
        ]
    lessons = {
        "status": "awaiting_sync",
        "file": str(LESSONS_FILE.relative_to(ROOT)),
        "lesson_count": 0,
        "updated_at": None,
    }
    if LESSONS_FILE.exists():
        text = LESSONS_FILE.read_text()
        lessons.update({
            "status": "synced",
            "lesson_count": sum(line.lstrip().startswith(("- ", "* ")) for line in text.splitlines()),
            "updated_at": datetime.fromtimestamp(
                LESSONS_FILE.stat().st_mtime, timezone.utc
            ).isoformat(),
        })
    latest_eval = None
    if LATEST_RSI_EVAL_JSON.exists():
        latest_eval = {"status": "measured", **json.loads(LATEST_RSI_EVAL_JSON.read_text())}
    else:
        metadata_files = list(VERIFIERS_EVAL_DIR.glob("**/metadata.json"))
    if latest_eval is None and metadata_files:
        latest_file = max(metadata_files, key=lambda path: path.stat().st_mtime)
        metadata = json.loads(latest_file.read_text())
        latest_eval = {
            "status": "measured",
            "model": metadata.get("model"),
            "avg_reward": metadata.get("avg_reward"),
            "avg_metrics": metadata.get("avg_metrics", {}),
            "num_examples": metadata.get("num_examples"),
            "rollouts_per_example": metadata.get("rollouts_per_example"),
            "rollout_count": (
                metadata.get("num_examples", 0) * metadata.get("rollouts_per_example", 0)
            ),
            "eval_seconds": metadata.get("time"),
            "source": str(latest_file.relative_to(ROOT)),
        }
    return {
        "schedule": [
            {"time": "8:00", "label": "Read digest"},
            {"time": "8:05", "label": "Pull lessons"},
            {"time": "8:15", "label": "Run one RSI cycle"},
            {"time": "8:45", "label": "Review trend"},
            {"time": "Human", "label": "Promote or reject"},
        ],
        "promotion": {"mode": "human", "flag": "--accepted true"},
        "lessons": lessons,
        "latest_eval": latest_eval,
        "telemetry": {
            "evidence_status": "imported",
            "source": str(MODEL_METRICS_CSV.relative_to(ROOT)),
            "updated_at": datetime.fromtimestamp(
                MODEL_METRICS_CSV.stat().st_mtime, timezone.utc
            ).isoformat(),
            "rows": metrics,
        },
    }


def rsi_idea_memory():
    """Return successful lessons and promotion count from hosted Supabase."""
    with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            select lesson, task_type, inserted_at
            from public.episodes
            where quality = 'good' and nullif(trim(lesson), '') is not null
            order by inserted_at desc
            limit 3
            """
        )
        ideas = [
            {key: json_value(value) for key, value in row.items()}
            for row in cursor.fetchall()
        ]
        cursor.execute(
            """
            select count(*) as promoted_count
            from public.rsi_runs
            where lower(coalesce(decision, '')) in
                  ('promote', 'promoted', 'accepted', 'champion')
            """
        )
        promoted_count = cursor.fetchone()["promoted_count"]
    return {
        "status": "live",
        "database": "hosted Supabase",
        "promoted_count": promoted_count,
        "ideas": ideas,
    }


def discord_rsi_messages():
    response = requests.get(
        f"https://discord.com/api/v10/channels/{DISCORD_RSI_CHANNEL_ID}/messages",
        params={"limit": 20},
        headers={"Authorization": f"Bot {os.environ['DISCORD_BOT_TOKEN']}"},
        timeout=10,
    )
    response.raise_for_status()
    messages = [
        {
            "id": row["id"],
            "content": row["content"],
            "created_at": row["timestamp"],
            "author": row["author"]["username"],
            "reactions": [
                {"emoji": reaction["emoji"]["name"], "count": reaction["count"]}
                for reaction in row.get("reactions", [])
            ],
        }
        for row in response.json()
        if row["content"].startswith(("**Actual RSI digest", "**Human promotion gate"))
    ]
    return {"status": "live", "channel": "daily", "messages": list(reversed(messages))}




def coordinator_json(path):
    response = requests.get(f"{COORDINATOR_URL}{path}", timeout=4)
    response.raise_for_status()
    return response.json()


def measured_radar():
    rows = coordinator_json("/api/radar")
    measured = [
        row for row in rows
        if isinstance(row, dict) and row.get("source") == "autoresearch-loop"
    ]
    if not measured:
        raise ValueError("coordinator has no live EC2 worker rows")
    return measured


def episodic_evidence(limit=16):
    """Recent Discord/user evidence persisted in hosted Supabase."""
    with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            select episode_id, channel, task_type, request, outcome, feedback,
                   quality, lesson, inserted_at
            from public.episodes
            order by inserted_at desc
            limit %s
            """,
            (limit,),
        )
        return [
            {key: json_value(value) for key, value in row.items()}
            for row in cursor.fetchall()
        ]


def harness_experiments(limit=200):
    """Measured evaluations and their explicit evidence links."""
    with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            select h.experiment_id, h.action, h.hypothesis, h.decision_quality,
                   h.seconds_per_answer, h.forbidden_platform_risk,
                   h.prompt_injection_risk, h.memory_diff_lines,
                   h.knowledge_regression, h.accepted, h.rolled_back, h.source_box,
                   h.evidence_episode_ids, h.research_urls, h.user_preference,
                   h.test_method, h.metadata, h.created_at,
                   s.stored_samples, s.stored_episodes
            from public.harness_experiments h
            left join (
              select evaluation_id, count(*) as stored_samples,
                     count(distinct episode_index) as stored_episodes
              from public.evaluation_samples
              group by evaluation_id
            ) s on s.evaluation_id = h.experiment_id
            where coalesce(h.metadata->>'hidden_from_evals', 'false') <> 'true'
            order by h.created_at asc
            limit %s
            """,
            (limit,),
        )
        return [
            {key: json_value(value) for key, value in row.items()}
            for row in cursor.fetchall()
        ]


def evaluation_samples(limit=500):
    """Compact, display-safe rollout details from the private sample store."""
    with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            select evaluation_id, sample_index, episode_index, rollout_number,
                   decision_quality, seconds_per_answer, prompt_injection_risk,
                   platform_violation_risk, successful, evaluated_at,
                   case
                     when payload ? 'task'
                     then ((payload->>'task')::jsonb)->>'prompt'
                     else payload->'prompt'->1->>'content'
                   end as prompt,
                   payload->'completion'->-1->>'content' as response
            from public.evaluation_samples
            order by evaluated_at asc, evaluation_id, episode_index, rollout_number,
                     sample_index
            limit %s
            """,
            (limit,),
        )
        return [
            {key: json_value(value) for key, value in row.items()}
            for row in cursor.fetchall()
        ]


def _response_summary(text):
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        payload = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        payload = {}
    return {
        "platform": str(payload.get("recommended_platform") or "Unparsed"),
        "condition": str(payload.get("condition") or ""),
        "lead_time_days": payload.get("lead_time_days"),
    }


def _group_evaluation_samples(rows):
    grouped = {}
    for row in rows:
        evaluation = grouped.setdefault(row["evaluation_id"], {})
        episode = evaluation.setdefault(row["episode_index"], {
            "episode_index": row["episode_index"],
            "prompt": row.get("prompt") or "Prompt unavailable",
            "rollouts": [],
        })
        episode["rollouts"].append({
            "rollout_number": row.get("rollout_number"),
            "decision_quality": row.get("decision_quality"),
            "seconds_per_answer": row.get("seconds_per_answer"),
            "prompt_injection_risk": row.get("prompt_injection_risk"),
            "platform_violation_risk": row.get("platform_violation_risk"),
            "successful": row.get("successful"),
            "evaluated_at": row.get("evaluated_at"),
            **_response_summary(row.get("response")),
        })
    output = {}
    for evaluation_id, episodes in grouped.items():
        output[evaluation_id] = []
        for episode in episodes.values():
            quality = [
                float(row["decision_quality"]) for row in episode["rollouts"]
                if row.get("decision_quality") is not None
            ]
            latency = [
                float(row["seconds_per_answer"]) for row in episode["rollouts"]
                if row.get("seconds_per_answer") is not None
            ]
            episode["decision_quality"] = (
                round(statistics.mean(quality), 4) if quality else None
            )
            episode["median_seconds"] = (
                round(statistics.median(latency), 3) if latency else None
            )
            output[evaluation_id].append(episode)
    return output


def soul_history(limit=50):
    """Versioned Hermes preferences; diff_lines is Evals metric four."""
    with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            select agent_name, version, diff_lines, summary, updated_at
            from public.agent_soul
            where agent_name = 'hermes'
            order by version asc
            limit %s
            """,
            (limit,),
        )
        return [
            {key: json_value(value) for key, value in row.items()}
            for row in cursor.fetchall()
        ]


def _feedback_summary(episode):
    feedback = episode.get("feedback") or {}
    if isinstance(feedback, dict):
        reactions = feedback.get("reactions") or []
        if reactions:
            return ", ".join(
                (
                    f"{row.get('emoji', 'reaction')} ×{row.get('count', 1)}"
                    if isinstance(row, dict) else str(row)
                )
                for row in reactions[:3]
            )
    return ""


def _registry_rows(rows):
    output = []
    for row in rows:
        metadata = row.get("metadata") or {}
        prompt_risk = row.get("prompt_injection_risk")
        output.append({
            "registry_id": row["experiment_id"],
            "source": "supabase-harness-registry",
            "ts": row["created_at"],
            "version": row["experiment_id"],
            "role": "champion" if row["accepted"] else "candidate",
            "accepted": row["accepted"],
            "rolled_back": row["rolled_back"],
            "stability": -float(row.get("knowledge_regression") or 0),
            "hypothesis": row.get("hypothesis") or row["action"].replace("_", " "),
            "accuracy": float(row.get("decision_quality") or 0),
            "retrieval_s": (
                float(row["seconds_per_answer"])
                if row.get("seconds_per_answer") is not None else None
            ),
            "prompt_injection_risk": (
                float(prompt_risk) if prompt_risk is not None else None
            ),
            "episodic_diff_lines": int(row.get("memory_diff_lines") or 0),
            "knowledge_regression": float(row.get("knowledge_regression") or 0),
            "episodes_tried": int(
                row.get("stored_episodes") or metadata.get("episodes_tried") or 0
            ),
            "stored_samples": int(
                row.get("stored_samples") or metadata.get("stored_samples") or 0
            ),
            "failed_rollouts": int(metadata.get("failed_rollouts") or 0),
            "n": int(metadata.get("rollouts") or 0),
        })
    return output


def _experiment_payload(rows, source, episodes=None, registry=None, samples=None):
    registry = registry or []
    sample_groups = _group_evaluation_samples(samples or [])
    registry_by_id = {row["experiment_id"]: row for row in registry}
    linked_ids = {row.get("registry_id") for row in rows}
    rows = [*rows, *[
        row for row in _registry_rows(registry)
        if row["registry_id"] not in linked_ids
    ]]
    rows.sort(key=lambda row: str(row.get("ts") or ""))
    clean = [row for row in rows if isinstance(row, dict) and isinstance(row.get("accuracy"), (int, float))]
    episodes_by_id = {row["episode_id"]: row for row in episodes or []}
    experiments = []
    for index, row in enumerate(clean, 1):
        stability = float(row.get("stability", 0) or 0)
        recorded = registry_by_id.get(row.get("registry_id"))
        evidence_ids = (recorded or {}).get("evidence_episode_ids") or []
        linked_episodes = [episodes_by_id[row_id] for row_id in evidence_ids if row_id in episodes_by_id]
        episode = linked_episodes[0] if linked_episodes else None
        memory_lines = int(
            (recorded or {}).get("memory_diff_lines")
            or row.get("episodic_diff_lines")
            or 0
        )
        description = row.get("hypothesis") or row.get("version", f"experiment {index}")
        preference = (recorded or {}).get("user_preference") or ""
        if not preference and episode:
            preference = _feedback_summary(episode) or episode.get("request") or episode.get("outcome") or ""
        research_urls = (recorded or {}).get("research_urls") or []
        experiments.append({
            **row,
            "experiment": index,
            "kept": bool(row.get("accepted") or row.get("role") == "champion"),
            "prompt_injection_risk": row.get("prompt_injection_risk"),
            "episodic_diff_lines": memory_lines,
            "knowledge_regression": round(
                float((recorded or {}).get("knowledge_regression") or max(0, -stability)),
                4,
            ),
            "episodes_tried": int(row.get("episodes_tried") or 0),
            "rollouts": int(row.get("n") or 0),
            "stored_samples": int(row.get("stored_samples") or 0),
            "failed_rollouts": int(row.get("failed_rollouts") or 0),
            "sample_episodes": sample_groups.get(row.get("registry_id"), []),
            "description": description,
            "evidence": {
                "source": "Supabase harness registry" if recorded else "EC2 experiment record",
                "source_detail": (
                    f"{recorded['action'].replace('_', ' ')} · {recorded.get('source_box') or 'orchestrator'}"
                    if recorded else "Legacy run · no explicit evidence link"
                ),
                "improvement": description,
                "preference": preference[:220] or "No linked Discord preference was recorded for this run.",
                "memory_change": (
                    f"{memory_lines} episodic memory line{'s' if memory_lines != 1 else ''} proposed"
                    if memory_lines else "No episodic memory patch attached"
                ),
                "tested_by": (
                    (recorded or {}).get("test_method")
                    or f"Verifiers golden set · {int(row.get('episodes_tried') or 0)} episodes · "
                       f"{int(row.get('n') or 0)} rollouts"
                ),
                "episode_ids": evidence_ids,
                "research_urls": research_urls,
            },
        })
    if not experiments:
        raise ValueError("no measured autoresearch rows")
    kept = [row for row in experiments if row["kept"]]
    current = experiments[-1]
    first = experiments[0]
    first_prompt_risk = next(
        (row["prompt_injection_risk"] for row in experiments if row["prompt_injection_risk"] is not None),
        None,
    )
    latest_prompt_risk = next(
        (row["prompt_injection_risk"] for row in reversed(experiments) if row["prompt_injection_risk"] is not None),
        None,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "seed": "live",
        "summary": {
            "experiments": len(experiments),
            "kept": len(kept),
            "accuracy_start": first["accuracy"],
            "accuracy_now": current["accuracy"],
            "retrieval_start": first.get("retrieval_s", 0),
            "retrieval_now": current.get("retrieval_s", 0),
            "prompt_injection_risk_start": first_prompt_risk,
            "prompt_injection_risk_now": latest_prompt_risk,
            "episodic_diff_start": first["episodic_diff_lines"],
            "episodic_diff_now": current["episodic_diff_lines"],
            "knowledge_regression_start": first["knowledge_regression"],
            "knowledge_regression_now": current["knowledge_regression"],
            "episodes_tried": sum(row["episodes_tried"] for row in experiments),
            "rollouts": sum(row["rollouts"] for row in experiments),
            "stored_samples": sum(row["stored_samples"] for row in experiments),
        },
        "experiments": experiments,
        "seed_justification": {"supabase_note": f"Live measured history from {source}"},
    }


def autoresearch_experiments():
    """Serve only timestamped evaluation history persisted in Supabase."""
    try:
        episodes = episodic_evidence()
    except Exception:
        episodes = []
    registry = harness_experiments()
    samples = evaluation_samples()
    return _experiment_payload(
        [],
        "live Supabase evaluations",
        episodes,
        registry,
        samples,
    )


def try_supabase_rsi_runs():
    """Best-effort read of public.rsi_runs when DB credentials exist."""
    try:
        with database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "select run_id, version, source, decision_quality, n_valid, n_total, "
                "decision, evaluated_at from public.rsi_runs order by evaluated_at asc"
            )
            rows = [
                {key: json_value(value) for key, value in row.items()}
                for row in cursor.fetchall()
            ]
        return {"status": "ok", "count": len(rows), "runs": rows}
    except Exception as error:
        # Surface measured CSV anchors so the UI can still justify the seed.
        csv_runs = []
        if RSI_RUNS_CSV.exists():
            with RSI_RUNS_CSV.open() as fh:
                for row in csv.DictReader(fh):
                    csv_runs.append({
                        "run_id": row.get("run_id"),
                        "version": row.get("version"),
                        "decision_quality": row.get("decision_quality"),
                        "median_latency_s": row.get("median_latency_s"),
                        "evaluated_at": row.get("evaluated_at"),
                        "source": "data/rsi_runs.csv",
                    })
        return {
            "status": "unavailable",
            "error": str(error),
            "runs": [],
            "csv_fallback": csv_runs,
            "prime_eval": json.loads(LATEST_RSI_EVAL_JSON.read_text())
            if LATEST_RSI_EVAL_JSON.exists() else None,
        }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            try:
                with database() as connection, connection.cursor() as cursor:
                    cursor.execute("select now()")
                    checked_at = cursor.fetchone()[0].isoformat()
                self.send_json({"status": "ok", "database": "hosted Supabase", "checked_at": checked_at})
            except Exception as error:
                self.send_json({"status": "error", "error": str(error)}, 503)
            return

        if parsed.path == "/api/marketplace":
            category = query.get("category", ["all"])[0].lower()
            if category not in {*CATEGORIES, "all"}:
                self.send_json({"error": "category must be gpu, macbook, ram, or all"}, 400)
                return
            try:
                self.send_json(marketplace(category))
            except Exception as error:
                self.send_json({"data_status": "unavailable", "error": str(error), "listings": []}, 503)
            return

        if parsed.path == "/api/autoresearch-experiments":
            try:
                self.send_json(autoresearch_experiments())
            except Exception as error:
                self.send_json({"error": str(error), "experiments": []}, 503)
            return

        if parsed.path == "/api/supabase-rsi-runs":
            self.send_json(try_supabase_rsi_runs())
            return

        if parsed.path == "/api/improvement":
            if not RSI_RUNS_CSV.exists():
                self.send_json({
                    "evidence_status": "illustrative",
                    "source": "built-in fallback",
                    "note": f"CSV unavailable: {RSI_RUNS_CSV}",
                    "runs": IMPROVEMENT_RUNS,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })
                return
            try:
                self.send_json(build_story(RSI_RUNS_CSV))
            except Exception as error:
                self.send_json({
                    "evidence_status": "invalid",
                    "source": str(RSI_RUNS_CSV),
                    "error": str(error),
                    "runs": [],
                }, 422)
            return

        if parsed.path == "/api/rsi-operations":
            try:
                self.send_json(rsi_operations())
            except Exception as error:
                self.send_json({"status": "invalid", "error": str(error)}, 422)
            return

        if parsed.path == "/api/rsi-ideas":
            try:
                self.send_json(rsi_idea_memory())
            except Exception as error:
                self.send_json({"status": "unavailable", "error": str(error), "ideas": []}, 503)
            return

        if parsed.path == "/api/research-evidence":
            try:
                self.send_json({
                    "status": "live",
                    "database": "hosted Supabase",
                    "episodes": episodic_evidence(),
                    "experiments": harness_experiments(),
                    "soul": soul_history(),
                })
            except Exception as error:
                self.send_json({"status": "unavailable", "error": str(error), "episodes": []}, 503)
            return

        if parsed.path == "/api/discord-rsi":
            try:
                self.send_json(discord_rsi_messages())
            except Exception as error:
                self.send_json({"status": "unavailable", "error": str(error)}, 503)
            return

        super().do_GET()

    def log_message(self, format, *args):
        print(f"[dashboard-api] {self.address_string()} {format % args}")


if __name__ == "__main__":
    load_env()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[dashboard-api] listening on http://127.0.0.1:{PORT}")
    server.serve_forever()
