#!/usr/bin/env python3
"""Validate recursive-improvement runs and prepare dashboard/video data."""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

FIELDS = (
    "step run_id version parent_version evaluated_at accepted baseline current "
    "evidence_status policy_change decision_quality decision_ci "
    "landed_price_error_pct landed_ci median_latency_s latency_ci "
    "valid_url_rate_pct url_ci unsupported_claims_pct claims_ci "
    "price_forecast_regret_usd regret_ci sample_size teacher_model"
).split()
BOOL_FIELDS = {"accepted", "baseline", "current"}
NUMBER_FIELDS = set(FIELDS[10:22]) | {"step", "sample_size"}
REQUIRED_NUMBER_FIELDS = {
    "step", "sample_size", "decision_quality", "decision_ci",
    "median_latency_s", "latency_ci",
}
PERCENT_FIELDS = {
    "landed_price_error_pct", "valid_url_rate_pct", "unsupported_claims_pct"
}


def boolean(value, field):
    value = str(value).strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{field} must be true or false")
    return value == "true"


def read_runs(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        rows = []
        for line, raw in enumerate(reader, 2):
            try:
                row = {field: raw.get(field, "").strip() for field in FIELDS}
                for field in BOOL_FIELDS:
                    row[field] = boolean(row[field], field)
                for field in NUMBER_FIELDS:
                    if not row[field] and field not in REQUIRED_NUMBER_FIELDS:
                        row[field] = None
                    else:
                        row[field] = int(row[field]) if field in {"step", "sample_size"} else float(row[field])
                datetime.fromisoformat(row["evaluated_at"].replace("Z", "+00:00"))
                rows.append(row)
            except Exception as error:
                raise ValueError(f"line {line}: {error}") from error
    validate(rows)
    return sorted(rows, key=lambda row: row["step"])


def validate(rows):
    if not rows:
        raise ValueError("at least one run is required")
    if len({row["run_id"] for row in rows}) != len(rows):
        raise ValueError("run_id values must be unique")
    if len({row["step"] for row in rows}) != len(rows):
        raise ValueError("step values must be unique")
    accepted = [row for row in rows if row["accepted"]]
    if not accepted:
        raise ValueError("at least one accepted run is required")
    if sum(row["baseline"] for row in accepted) != 1:
        raise ValueError("accepted runs need exactly one baseline")
    if sum(row["current"] for row in accepted) != 1:
        raise ValueError("accepted runs need exactly one current champion")
    if any(row["current"] and not row["accepted"] for row in rows):
        raise ValueError("the current champion must be accepted")
    for row in rows:
        if row["evidence_status"] not in {"measured", "illustrative"}:
            raise ValueError("evidence_status must be measured or illustrative")
        if not 0 <= row["decision_quality"] <= 1:
            raise ValueError(f"{row['run_id']}: decision_quality must be 0..1")
        for field in PERCENT_FIELDS:
            if row[field] is not None and not 0 <= row[field] <= 100:
                raise ValueError(f"{row['run_id']}: {field} must be 0..100")
        for field in NUMBER_FIELDS - {"step"}:
            if row[field] is not None and row[field] < 0:
                raise ValueError(f"{row['run_id']}: {field} must be non-negative")


def accepted_run(row):
    return {
        "step": row["step"],
        "run_id": row["run_id"],
        "version": row["version"],
        "label": row["policy_change"],
        "current": row["current"],
        "baseline": row["baseline"],
        "decision_quality": row["decision_quality"],
        "decision_ci": row["decision_ci"],
        "landed_price_error": row["landed_price_error_pct"],
        "landed_ci": row["landed_ci"],
        "latency": row["median_latency_s"],
        "latency_ci": row["latency_ci"],
        "valid_url_rate": row["valid_url_rate_pct"],
        "url_ci": row["url_ci"],
        "unsupported_claims": row["unsupported_claims_pct"],
        "claims_ci": row["claims_ci"],
        "forecast_regret": row["price_forecast_regret_usd"],
        "regret_ci": row["regret_ci"],
        "sample_size": row["sample_size"],
        "teacher_model": row["teacher_model"],
    }


def build_story(path):
    rows = read_runs(path)
    statuses = {row["evidence_status"] for row in rows}
    status = next(iter(statuses)) if len(statuses) == 1 else "mixed"
    accepted = [accepted_run(row) for row in rows if row["accepted"]]
    candidates = [
        {
            "step": row["step"],
            "run_id": row["run_id"],
            "version": row["version"],
            "parent_version": row["parent_version"],
            "accepted": row["accepted"],
            "decision_quality": row["decision_quality"],
            "policy_change": row["policy_change"],
            "evaluated_at": row["evaluated_at"],
        }
        for row in rows
    ]
    return {
        "evidence_status": status,
        "source": str(Path(path)),
        "note": (
            "Measured from Verifiers rollout outputs."
            if status == "measured"
            else "Illustrative fixture; replace it with measured Verifiers runs."
        ),
        "runs": list(reversed(accepted)),
        "candidates": candidates,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--prompt-template", type=Path)
    parser.add_argument("--prompt-out", type=Path)
    parser.add_argument("--project-name", default="Decision Frontier")
    parser.add_argument("--teacher-model", default="Nemotron")
    parser.add_argument("--output-video", default="artifacts/rsi-evolution.mp4")
    args = parser.parse_args()
    story = build_story(args.csv_path)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(story, indent=2) + "\n")
    if args.prompt_out:
        if not args.prompt_template:
            parser.error("--prompt-template is required with --prompt-out")
        prompt = args.prompt_template.read_text()
        replacements = {
            "{{PROJECT_NAME}}": args.project_name,
            "{{CSV_PATH}}": str(args.csv_path),
            "{{TEACHER_MODEL}}": args.teacher_model,
            "{{OUTPUT_PATH}}": args.output_video,
        }
        for key, value in replacements.items():
            prompt = prompt.replace(key, value)
        args.prompt_out.parent.mkdir(parents=True, exist_ok=True)
        args.prompt_out.write_text(prompt)
    print(f"validated {len(story['candidates'])} candidates; {len(story['runs'])} accepted")


if __name__ == "__main__":
    main()
