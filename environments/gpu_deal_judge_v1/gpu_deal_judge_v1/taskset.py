"""Decision Frontier purchase-decision benchmark."""

import json
import re
from pathlib import Path
from typing import Any

import verifiers.v1 as vf

BASE_SYSTEM = """You are a PC purchase-decision judge.
Given a buyer request, decide where and how to buy. Respond with ONLY a JSON
object: {"recommended_platform": str, "condition": str,
"lead_time_days": int, "reasons": [str, str]}.
Be conservative about warranty, condition, seller quality, and delivery claims."""


class GPUDealData(vf.TaskData):
    expected_platform: str
    ground_truth: dict[str, Any]


def _extract_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


class GPUDealTask(vf.Task[GPUDealData]):
    @vf.reward(weight=1.0)
    async def decision_quality(self, trace: vf.Trace) -> float:
        prediction = _extract_json(trace.last_reply)
        if prediction is None:
            trace.record_metrics(
                {
                    "valid_json_rate_pct": 0.0,
                    "avoided_platform_violation_pct": 0.0,
                }
            )
            return 0.0

        truth = self.data.ground_truth
        platform = str(prediction.get("recommended_platform", "")).lower()
        avoided = [str(item).lower() for item in truth.get("avoid_platforms", [])]
        violated = bool(
            platform and any(item in platform or platform in item for item in avoided)
        )

        score = 0.0 if violated else 0.4
        expected = self.data.expected_platform.lower().replace(" or ", ",")
        options = [item.strip() for item in expected.split(",") if item.strip()]
        if platform and any(
            option in platform or platform in option for option in options
        ):
            score += 0.3

        expected_condition = str(truth.get("condition", "")).lower()
        actual_condition = str(prediction.get("condition", "")).lower()
        if (
            expected_condition
            and actual_condition
            and (
                expected_condition in actual_condition
                or actual_condition in expected_condition
            )
        ):
            score += 0.2

        max_lead_time = truth.get("max_lead_time_days")
        if max_lead_time is not None:
            try:
                score += (
                    0.1
                    if int(prediction.get("lead_time_days", 10**6))
                    <= int(max_lead_time)
                    else 0.0
                )
            except (TypeError, ValueError):
                pass

        trace.record_metrics(
            {
                "valid_json_rate_pct": 100.0,
                "avoided_platform_violation_pct": 100.0 if violated else 0.0,
            }
        )
        return round(score, 3)


class GPUDealConfig(vf.TasksetConfig):
    task: vf.TaskConfig = vf.TaskConfig()
    system_prompt: str = BASE_SYSTEM
    lessons: str = ""


class GPUDealJudgeTaskset(vf.Taskset[GPUDealTask, GPUDealConfig]):
    def load(self) -> list[GPUDealTask]:
        path = Path(__file__).with_name("data") / "golden_dataset.json"
        cases = json.loads(path.read_text())
        system_prompt = self.config.system_prompt
        if self.config.lessons.strip():
            system_prompt += (
                "\n\nLessons from prior graded interactions:\n"
                + self.config.lessons.strip()
            )

        return [
            GPUDealTask(
                GPUDealData(
                    idx=index,
                    name=case["name"],
                    prompt=case["prompt"],
                    system_prompt=system_prompt,
                    expected_platform=case["expected_platform"],
                    ground_truth=case["ground_truth"],
                ),
                self.config.task,
            )
            for index, case in enumerate(cases)
        ]
