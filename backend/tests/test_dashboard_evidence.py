import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from dashboard_api import (  # noqa: E402
    _experiment_payload,
    _group_evaluation_samples,
    cached,
    evaluation_table,
)


class EvidencePayloadTest(unittest.TestCase):
    def test_renamed_evaluation_table_is_preferred(self):
        class Cursor:
            def execute(self, _query, params):
                self.table = params[0]

            def fetchone(self):
                return {"present": self.table == "evaluation_verifiers"}

        self.assertEqual(evaluation_table(Cursor()), "evaluation_verifiers")

    def test_registry_links_only_explicit_episode(self):
        episode = {
            "episode_id": "discord:daily:1",
            "channel": "daily",
            "request": "Prefer online delivery.",
            "feedback": {"reactions": [{"emoji": "👍", "count": 2}]},
        }
        registry = [{
            "experiment_id": "run:exp-1",
            "action": "mutate_policy",
            "hypothesis": "Filter pickup-only offers",
            "decision_quality": .7,
            "seconds_per_answer": 2.1,
            "forbidden_platform_risk": 0,
            "prompt_injection_risk": None,
            "memory_diff_lines": 4,
            "knowledge_regression": 0,
            "accepted": True,
            "rolled_back": False,
            "source_box": "cursor-karpathy",
            "evidence_episode_ids": [episode["episode_id"]],
            "research_urls": [],
            "user_preference": "",
            "test_method": "Frozen golden set",
            "metadata": {"episodes_tried": 15, "rollouts": 30, "stored_samples": 30},
            "created_at": "2026-07-19T00:00:00Z",
        }]
        rows = [{
            "registry_id": "run:exp-1",
            "ts": "2026-07-19T00:00:00Z",
            "version": "exp-1",
            "accepted": True,
            "accuracy": .7,
            "retrieval_s": 2.1,
            "prompt_injection_risk": None,
            "stability": 0,
            "episodes_tried": 15,
            "stored_samples": 30,
            "n": 30,
        }]

        point = _experiment_payload(rows, "test", [episode], registry)["experiments"][0]

        self.assertEqual(point["evidence"]["source"], "Supabase harness registry")
        self.assertEqual(point["evidence"]["episode_ids"], [episode["episode_id"]])
        self.assertEqual(point["evidence"]["preference"], "👍 ×2")
        self.assertEqual(point["episodic_diff_lines"], 4)
        self.assertEqual(point["episodes_tried"], 15)
        self.assertIsNone(point["prompt_injection_risk"])
        self.assertIn("4 episodic memory lines", point["evidence"]["memory_change"])

    def test_legacy_run_is_not_given_unrelated_evidence(self):
        payload = _experiment_payload(
            [{"accuracy": .5, "retrieval_s": 3, "deal_safety": 100, "version": "legacy"}],
            "test",
            [{"episode_id": "unrelated", "request": "Do not attach me"}],
            [],
        )
        point = payload["experiments"][0]
        self.assertEqual(point["evidence"]["episode_ids"], [])
        self.assertIn("no explicit evidence link", point["evidence"]["source_detail"])

    def test_samples_are_grouped_by_evaluation_and_episode(self):
        groups = _group_evaluation_samples([
            {
                "evaluation_id": "eval-1",
                "episode_index": 2,
                "rollout_number": 1,
                "decision_quality": .8,
                "seconds_per_answer": 4,
                "successful": True,
                "prompt": "Find a safe GPU.",
                "response": '{"recommended_platform":"Best Buy","condition":"new","lead_time_days":2}',
            },
            {
                "evaluation_id": "eval-1",
                "episode_index": 2,
                "rollout_number": 2,
                "decision_quality": .6,
                "seconds_per_answer": 6,
                "successful": True,
                "prompt": "Find a safe GPU.",
                "response": '{"recommended_platform":"Newegg","condition":"new","lead_time_days":3}',
            },
        ])
        episode = groups["eval-1"][0]
        self.assertEqual(episode["prompt"], "Find a safe GPU.")
        self.assertEqual(episode["decision_quality"], .7)
        self.assertEqual(episode["median_seconds"], 5)
        self.assertEqual(episode["rollouts"][0]["platform"], "Best Buy")

    def test_payload_exposes_live_loop_and_git_provenance(self):
        registry = [{
            "experiment_id": "exp-injection-resist",
            "action": "mutate_policy",
            "hypothesis": "Resist listing injections",
            "decision_quality": .7,
            "seconds_per_answer": 2,
            "prompt_injection_risk": 0,
            "memory_diff_lines": 3,
            "knowledge_regression": -.03,
            "accepted": True,
            "rolled_back": False,
            "source_box": "autoresearch-v2",
            "evidence_episode_ids": [],
            "research_urls": [],
            "user_preference": "",
            "test_method": "Paired golden set",
            "metadata": {"episodes_tried": 15, "rollouts": 15},
            "created_at": "2026-07-19T00:00:00Z",
        }]
        soul = [{
            "agent_name": "hermes",
            "version": 4,
            "diff_lines": 3,
            "summary": "promoted exp-injection-resist (git 757dbb6)",
        }]

        payload = _experiment_payload([], "test", registry=registry, soul=soul)

        self.assertEqual(payload["loops"]["latest_source"], "autoresearch-v2")
        self.assertEqual(payload["loops"]["git_hash"], "757dbb6")
        self.assertEqual(payload["experiments"][0]["evidence"]["git_hash"], "757dbb6")
        self.assertEqual(payload["summary"]["episodes_tried"], 15)
        self.assertEqual(payload["experiments"][0]["knowledge_regression"], .03)

    def test_process_cache_reuses_loaded_value(self):
        calls = []
        key = f"test:{id(calls)}"

        first = cached(key, 30, lambda: calls.append(1) or {"value": 1})
        second = cached(key, 30, lambda: calls.append(2) or {"value": 2})

        self.assertEqual(first, second)
        self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()
