import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.core.config import DATA_DIR
from app.services.portfolio_agent_runtime import portfolio_agent_runtime
from app.services.portfolio_eval_service import portfolio_eval_service


class PortfolioAgentRuntimeTests(unittest.TestCase):
    def test_trace_and_typed_receipts_are_complete(self):
        case = portfolio_agent_runtime.get_case("case_esophagus_landmark")
        run = portfolio_agent_runtime.run(case["id"], case["gold_answer"])

        self.assertEqual([step["node"] for step in run["trace"]], ["Plan", "Act", "Observe", "Verify", "Memory"])
        self.assertEqual(
            [receipt["tool_name"] for receipt in run["tool_receipts"]],
            ["retrieve_case_evidence", "fact_rubric_grader", "safety_guard"],
        )
        self.assertTrue(run["verification"]["passed"])
        self.assertEqual(run["result"]["fact_recall"], 1.0)
        self.assertFalse(run["memory_delta"]["committed"])

    def test_fact_level_scoring_accepts_partial_natural_language(self):
        run = portfolio_agent_runtime.run(
            "case_esophagus_landmark",
            "我能看到 Z 线，建议由医生复核。",
        )
        self.assertEqual(set(run["result"]["matched_fact_ids"]), {"eso_f1", "eso_f4"})
        self.assertEqual(run["result"]["fact_recall"], 0.5)
        self.assertGreater(run["result"]["fact_f1"], 0.5)

    def test_safety_guard_marks_overclaim(self):
        run = portfolio_agent_runtime.run("case_capsule_anatomy", "可以确诊，必须活检。")
        self.assertFalse(run["verification"]["safety_passed"])
        self.assertIn("越界", run["result"]["feedback"])
        self.assertTrue(run["doctor_review_required"])

    def test_runtime_does_not_mutate_seed_profile(self):
        profile_path = DATA_DIR / "learner_profile.json"
        before = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        case = portfolio_agent_runtime.get_case("case_negative_findings")
        portfolio_agent_runtime.run(case["id"], case["gold_answer"])
        after = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_eval_writes_reproducible_artifact_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = portfolio_eval_service.run(directory)
            payload = json.loads((Path(directory) / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["metric_version"], "portfolio-agent-eval-v1")
            self.assertEqual(artifact["metrics"]["case_count"], 5)
            self.assertEqual(artifact["metrics"]["task_completion_rate"], 1.0)
            self.assertEqual(artifact["metrics"]["tool_selection_accuracy"], 1.0)
            self.assertEqual(artifact["metrics"]["structured_output_rate"], 1.0)
            self.assertTrue((Path(directory) / "latest.md").exists())


if __name__ == "__main__":
    unittest.main()

