#!/usr/bin/env python3
"""Aggregate Verifiers RolloutOutput JSON/JSONL into one RSI candidate row."""

import argparse
import csv
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from prepare_rsi_story import FIELDS

METRICS = (
    "decision_quality landed_price_error_pct valid_url_rate_pct "
    "unsupported_claims_pct price_forecast_regret_usd"
).split()


def load_outputs(path):
    text = Path(path).read_text().strip()
    try:
        values = json.loads(text)
    except json.JSONDecodeError:
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    values = values if isinstance(values, list) else values.get("outputs", [values])
    rows = [row for row in values if row.get("is_completed", True)]
    if not rows:
        raise ValueError("no completed rollout outputs found")
    return rows


def mean_ci(values):
    mean = statistics.fmean(values)
    ci = 0 if len(values) < 2 else 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return round(mean, 6), round(ci, 6)


def median_ci(values, rounds=1500):
    center = statistics.median(values)
    if len(values) < 2:
        return center, 0
    rng = random.Random(2026)
    estimates = sorted(
        statistics.median(rng.choices(values, k=len(values))) for _ in range(rounds)
    )
    low, high = estimates[int(.025 * rounds)], estimates[int(.975 * rounds)]
    return round(center, 6), round(max(center - low, high - center), 6)


def flag(value):
    return str(value).lower() == "true"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--parent-version", default="")
    parser.add_argument("--policy-change", required=True)
    parser.add_argument("--teacher-model", default="Nemotron")
    parser.add_argument("--accepted", choices=["true", "false"], default="false")
    parser.add_argument("--baseline", choices=["true", "false"], default="false")
    parser.add_argument("--current", choices=["true", "false"], default="false")
    parser.add_argument("--reset", action="store_true", help="replace the output CSV")
    args = parser.parse_args()
    if flag(args.current) and not flag(args.accepted):
        parser.error("--current true requires --accepted true")

    outputs = load_outputs(args.results)
    aggregates = {}
    for metric in METRICS:
        values = [
            row.get("metrics", {}).get(
                metric,
                row.get("rewards", {}).get(metric, row.get("reward")),
            )
            for row in outputs
        ]
        if metric == "decision_quality":
            values = [float(value or 0) for value in values]
        else:
            values = [float(value) for value in values if value is not None]
        aggregates[metric] = mean_ci(values) if len(values) == len(outputs) else (None, None)
    def _latency_s(row):
        t = row.get("timing", {}) or {}
        if "total_ms" in t:
            return float(t["total_ms"]) / 1000
        if "total" in t:
            return float(t["total"])
        scoring = t.get("scoring", {})
        if t.get("start") is not None and scoring.get("end") is not None:
            return float(scoring["end"]) - float(t["start"])
        return 0.0
    latency = median_ci([_latency_s(row) for row in outputs])

    existing = []
    if args.output.exists() and not args.reset:
        with args.output.open(newline="", encoding="utf-8-sig") as source:
            existing = list(csv.DictReader(source))
    if any(row.get("run_id") == args.run_id for row in existing):
        raise ValueError(f"run_id already exists: {args.run_id}")
    if flag(args.current):
        for row in existing:
            row["current"] = "false"
    row = {
        "step": max((int(item["step"]) for item in existing), default=-1) + 1,
        "run_id": args.run_id,
        "version": args.version,
        "parent_version": args.parent_version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "accepted": args.accepted,
        "baseline": args.baseline,
        "current": args.current,
        "evidence_status": "measured",
        "policy_change": args.policy_change,
        "decision_quality": aggregates["decision_quality"][0],
        "decision_ci": aggregates["decision_quality"][1],
        "landed_price_error_pct": aggregates["landed_price_error_pct"][0],
        "landed_ci": aggregates["landed_price_error_pct"][1],
        "median_latency_s": latency[0],
        "latency_ci": latency[1],
        "valid_url_rate_pct": aggregates["valid_url_rate_pct"][0],
        "url_ci": aggregates["valid_url_rate_pct"][1],
        "unsupported_claims_pct": aggregates["unsupported_claims_pct"][0],
        "claims_ci": aggregates["unsupported_claims_pct"][1],
        "price_forecast_regret_usd": aggregates["price_forecast_regret_usd"][0],
        "regret_ci": aggregates["price_forecast_regret_usd"][1],
        "sample_size": len(outputs),
        "teacher_model": args.teacher_model,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(existing + [row])
    print(f"added {args.run_id}: n={len(outputs)}, decision_quality={row['decision_quality']:.3f}")


if __name__ == "__main__":
    main()
