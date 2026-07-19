import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from dashboard_api import _experiment_payload  # noqa: E402


class EvidencePayloadTest(unittest.TestCase):
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
            "memory_diff_lines": 4,
            "knowledge_regression": 0,
            "accepted": True,
            "rolled_back": False,
            "source_box": "cursor-karpathy",
            "evidence_episode_ids": [episode["episode_id"]],
            "research_urls": [],
            "user_preference": "",
            "test_method": "Frozen golden set",
            "metadata": {"rollouts": 30},
            "created_at": "2026-07-19T00:00:00Z",
        }]
        rows = [{
            "registry_id": "run:exp-1",
            "ts": "2026-07-19T00:00:00Z",
            "version": "exp-1",
            "accepted": True,
            "accuracy": .7,
            "retrieval_s": 2.1,
            "deal_safety": 100,
            "stability": 0,
            "n": 30,
        }]

        soul = [{"agent_name": "hermes", "version": 2, "diff_lines": 2,
                 "summary": "Learned online-only preference"}]
        point = _experiment_payload(rows, "test", [episode], registry, soul)["experiments"][0]

        self.assertEqual(point["evidence"]["source"], "Supabase harness registry")
        self.assertEqual(point["evidence"]["episode_ids"], [episode["episode_id"]])
        self.assertEqual(point["evidence"]["preference"], "👍 ×2")
        self.assertEqual(point["episodic_diff_lines"], 2)
        self.assertIn("Hermes SOUL v2", point["evidence"]["memory_change"])

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


if __name__ == "__main__":
    unittest.main()
