"""GPU deal-judge verifiers environment.

Wraps the golden dataset (scripts/golden_dataset.json) as a verifiers
SingleTurnEnv so `vf-eval` can generate scored rollouts against any
OpenAI-compatible endpoint (we use NVIDIA's hosted Nemotron).

The POLICY VARIABLE between eval runs is the episodic-memory lessons file:
pass `memory_file` to inject the current "Learned lessons" into the system
prompt — memory-ON vs memory-OFF on the same frozen dataset is the RSI claim,
and each run becomes one point on the dashboard trend line
(scripts/verifiers_to_rsi_csv.py -> data/rsi_runs.csv).
"""

import json
import re
from pathlib import Path

import verifiers as vf
from datasets import Dataset

def _find_golden() -> Path:
    """Resolve the golden dataset whether the env runs from a repo checkout
    or as an installed package: env var > cwd upward search > __file__."""
    import os
    if os.environ.get("GOLDEN_DATASET"):
        return Path(os.environ["GOLDEN_DATASET"])
    for base in [Path.cwd(), *Path.cwd().parents]:
        p = base / "scripts" / "golden_dataset.json"
        if p.exists():
            return p
    return Path(__file__).resolve().parents[2] / "scripts" / "golden_dataset.json"

GOLDEN = _find_golden()

BASE_SYSTEM = """You are a GPU purchase-decision judge for a buying-assistant team.
Given a buyer request, decide where and how to buy. Respond with ONLY a JSON
object: {"recommended_platform": str, "condition": str,
"lead_time_days": int, "reasons": [str, str]}.
Platforms: Amazon (Direct), Amazon Marketplace Third-Party, eBay, Newegg,
Best Buy, Micro Center. Be conservative about warranty and delivery claims."""


def _lessons_block(memory_file: str | None) -> str:
    if not memory_file:
        return ""
    p = Path(memory_file)
    if not p.exists():
        return ""
    return "\n\nLessons learned from prior graded interactions:\n" + p.read_text()


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def load_environment(memory_file: str | None = None, **kwargs) -> vf.Environment:
    cases = json.loads(GOLDEN.read_text())
    dataset = Dataset.from_list([
        {
            "question": c["prompt"],
            "answer": json.dumps({
                "expected_platform": c.get("expected_platform", ""),
                **c.get("ground_truth", {}),
            }),
            "task": "gpu-deal-judge",
        }
        for c in cases
    ])

    parser = vf.Parser(extract_fn=lambda t: t)

    def decision_quality(completion, answer, **_) -> float:
        """Weighted policy score in [0,1]: platform safety 0.4, platform
        match 0.3, condition 0.2, lead time 0.1."""
        text = completion[-1]["content"] if isinstance(completion, list) else str(completion)
        pred = _extract_json(text)
        truth = json.loads(answer)
        if pred is None:
            return 0.0
        score = 0.0
        plat = str(pred.get("recommended_platform", "")).lower()
        avoid = [a.lower() for a in truth.get("avoid_platforms", [])]
        if plat and not any(a in plat or plat in a for a in avoid):
            score += 0.4
        expected = str(truth.get("expected_platform", "")).lower()
        if plat and expected and any(p.strip() in plat for p in expected.replace(" or ", ",").split(",") if p.strip()):
            score += 0.3
        cond_t = str(truth.get("condition", "")).lower()
        cond_p = str(pred.get("condition", "")).lower()
        if cond_t and (cond_t in cond_p or cond_p in cond_t):
            score += 0.2
        try:
            if int(pred.get("lead_time_days", 99)) <= int(truth.get("max_lead_time_days", 99)):
                score += 0.1
        except (TypeError, ValueError):
            pass
        return round(score, 3)

    def valid_json_rate_pct(completion, **_) -> float:
        text = completion[-1]["content"] if isinstance(completion, list) else str(completion)
        return 100.0 if _extract_json(text) is not None else 0.0

    def avoided_platform_violation_pct(completion, answer, **_) -> float:
        text = completion[-1]["content"] if isinstance(completion, list) else str(completion)
        pred = _extract_json(text) or {}
        plat = str(pred.get("recommended_platform", "")).lower()
        avoid = [a.lower() for a in json.loads(answer).get("avoid_platforms", [])]
        return 100.0 if plat and any(a in plat or plat in a for a in avoid) else 0.0

    rubric = vf.Rubric(parser=parser)
    rubric.add_reward_func(decision_quality, weight=1.0)
    rubric.add_reward_func(valid_json_rate_pct, weight=0.0)
    rubric.add_reward_func(avoided_platform_violation_pct, weight=0.0)

    return vf.SingleTurnEnv(
        dataset=dataset,
        system_prompt=BASE_SYSTEM + _lessons_block(memory_file),
        parser=parser,
        rubric=rubric,
        **kwargs,
    )
