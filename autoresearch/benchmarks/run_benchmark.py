#!/usr/bin/env python3
"""Benchmark harness for the self-improving review judge (Sage).

Scores a model+memory version against the Ott OpSpam v1.4 deceptive-review
corpus (gold labels) and writes a versioned scorecard to benchmarks/results/.

Design (see docs/self-improving-review-judge.md):
- Held-out test slice: fold5 of all four quadrants (320 reviews), sampled
  deterministically to --sample items (balanced across quadrants).
- v0 baseline runs with NO memory; later versions pass --memory lessons.md
  whose contents are injected into the system prompt. The delta between
  memory-off and memory-on on the SAME frozen slice is the learning claim.
- Data must never enter agent memory; this script only reads it at eval time.

Usage:
  NVIDIA_INFERENCE_API_KEY=... python3 run_benchmark.py --version v0 [--sample 100]
  python3 run_benchmark.py --version v3 --memory ../memory/lessons.md
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "nvidia/nemotron-3-super-120b-a12b"
DATA = Path(__file__).parent / "data" / "op_spam_v1.4"
RESULTS = Path(__file__).parent / "results"

QUADRANTS = {
    ("positive_polarity", "deceptive_from_MTurk"): "deceptive",
    ("positive_polarity", "truthful_from_TripAdvisor"): "truthful",
    ("negative_polarity", "deceptive_from_MTurk"): "deceptive",
    ("negative_polarity", "truthful_from_Web"): "truthful",
}

SYSTEM_PROMPT = (
    "You are a review-authenticity judge. Classify the hotel review as "
    "written by a genuine guest (truthful) or fabricated by someone who "
    "never stayed there (deceptive). Answer with exactly one word: "
    "truthful or deceptive."
)


def load_test_slice(sample_per_quadrant: int):
    items = []
    for (polarity, source), label in QUADRANTS.items():
        fold = DATA / polarity / source / "fold5"
        files = sorted(fold.glob("*.txt"))
        rng = random.Random(2026)  # fixed seed: slice is frozen across versions
        picked = rng.sample(files, min(sample_per_quadrant, len(files)))
        for f in picked:
            items.append({"id": f"{polarity}/{source}/{f.name}",
                          "text": f.read_text(errors="replace").strip(),
                          "label": label})
    return items


def ask_model(api_key: str, system: str, review: str, retries: int = 3) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": f"Review:\n{review}\n\nOne word answer:"}],
        "temperature": 0,
        "max_tokens": 2000,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.load(r)
            return out["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - retry any transient failure
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return ""


def parse_verdict(text: str) -> str:
    m = re.findall(r"\b(truthful|deceptive)\b", text.lower())
    return m[-1] if m else "unparsed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="memory version tag, e.g. v0")
    ap.add_argument("--sample", type=int, default=100, help="total items (split /4)")
    ap.add_argument("--memory", help="lessons file injected into the system prompt")
    args = ap.parse_args()

    api_key = os.environ.get("NVIDIA_INFERENCE_API_KEY") or os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        sys.exit("Set NVIDIA_INFERENCE_API_KEY (or NVIDIA_API_KEY) in the environment.")

    system = SYSTEM_PROMPT
    memory_note = "none (baseline)"
    if args.memory:
        lessons = Path(args.memory).read_text()
        system += "\n\nLessons learned from prior graded interactions:\n" + lessons
        memory_note = args.memory

    items = load_test_slice(args.sample // 4)
    print(f"[{args.version}] {len(items)} items, memory: {memory_note}", flush=True)

    tp = fp = tn = fn = unparsed = 0
    records = []
    for i, item in enumerate(items, 1):
        verdict = parse_verdict(ask_model(api_key, system, item["text"]))
        gold = item["label"]
        if verdict == "unparsed":
            unparsed += 1
        elif verdict == "deceptive" and gold == "deceptive":
            tp += 1
        elif verdict == "deceptive" and gold == "truthful":
            fp += 1
        elif verdict == "truthful" and gold == "truthful":
            tn += 1
        else:
            fn += 1
        records.append({"id": item["id"], "gold": gold, "pred": verdict})
        if i % 10 == 0:
            print(f"  {i}/{len(items)} done", flush=True)

    n = tp + fp + tn + fn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    RESULTS.mkdir(exist_ok=True)
    summary = {
        "version": args.version, "model": MODEL, "memory": memory_note,
        "n_scored": n, "unparsed": unparsed, "accuracy": round(acc, 4),
        "precision_deceptive": round(prec, 4), "recall_deceptive": round(rec, 4),
        "f1_deceptive": round(f1, 4),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "dataset": "OpSpam v1.4 fold5 (frozen slice, seed 2026)",
    }
    (RESULTS / f"{args.version}.json").write_text(
        json.dumps({"summary": summary, "predictions": records}, indent=2))
    (RESULTS / f"{args.version}.md").write_text(
        f"# Benchmark scorecard {args.version}\n\n"
        f"- Model: `{MODEL}` · Memory: {memory_note}\n"
        f"- Dataset: OpSpam v1.4, frozen fold5 slice (seed 2026), n={n} "
        f"(unparsed: {unparsed})\n\n"
        f"| Accuracy | Precision (dec) | Recall (dec) | F1 (dec) |\n"
        f"|---|---|---|---|\n"
        f"| {acc:.3f} | {prec:.3f} | {rec:.3f} | {f1:.3f} |\n\n"
        f"Confusion: TP={tp} FP={fp} TN={tn} FN={fn}\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
