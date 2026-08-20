import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import DATA_DIR
from app.main import app
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

    def test_sparse_retrieval_returns_ranked_explainable_evidence(self):
        result = portfolio_agent_runtime.retrieve_evidence(
            "食管 Z 线解剖标志",
            top_k=3,
            metadata_filters={"source_dataset": "Kvasir-VQA-x1", "body_part": "食管"},
        )
        self.assertEqual(result["retrieval_mode"], "explainable_sparse_bm25_equivalent")
        self.assertEqual(result["items"][0]["evidence_id"], "eso_f1")
        self.assertGreater(result["items"][0]["score"], 0)
        self.assertEqual(result["items"][0]["rank"], 1)

    def test_tool_timeout_recovers_once_and_emits_recovery_trace(self):
        case = portfolio_agent_runtime.get_case("case_polyp_followup")
        run = portfolio_agent_runtime.run(
            case["id"],
            case["gold_answer"],
            failure_injection={"tool_name": "retrieve_case_evidence", "error_code": "timeout"},
        )
        retrieval_receipts = [item for item in run["tool_receipts"] if item["tool_name"] == "retrieve_case_evidence"]
        self.assertEqual(len(retrieval_receipts), 2)
        self.assertFalse(retrieval_receipts[0]["success"])
        self.assertEqual(retrieval_receipts[0]["error_code"], "timeout")
        self.assertTrue(retrieval_receipts[1]["success"])
        self.assertEqual(retrieval_receipts[1]["attempt"], 2)
        self.assertIn("Recovery", [step["node"] for step in run["trace"]])
        self.assertTrue(run["verification"]["recovery_succeeded"])

    def test_context_manifest_and_rule_usage_are_explicit(self):
        case = portfolio_agent_runtime.get_case("case_instrument_field")
        run = portfolio_agent_runtime.run(case["id"], case["gold_answer"], context_budget_tokens=64)
        manifest = run["context_manifest"]
        self.assertEqual(manifest["budget_tokens"], 64)
        self.assertLessEqual(manifest["included_estimated_tokens"], 64)
        self.assertTrue(any(not chunk["included"] for chunk in manifest["chunks"]))
        self.assertEqual(run["usage_ledger"]["model_calls"], 0)
        self.assertIsNone(run["usage_ledger"]["provider_usage"])
        self.assertIsNone(run["usage_ledger"]["estimated_cost"])

    def test_session_checkpoint_replays_same_input_without_seed_write(self):
        case = portfolio_agent_runtime.get_case("case_capsule_anatomy")
        source = portfolio_agent_runtime.run(case["id"], case["gold_answer"])
        replay = portfolio_agent_runtime.replay(source["run_id"])
        self.assertEqual(replay["parent_run_id"], source["run_id"])
        self.assertEqual(replay["replay_id"], replay["run_id"])
        self.assertEqual(replay["case_id"], source["case_id"])
        self.assertEqual(replay["checkpoint"]["input_hash"], source["checkpoint"]["input_hash"])

    def test_ndjson_endpoint_streams_real_stages_and_final_run(self):
        case = portfolio_agent_runtime.get_case("case_esophagus_landmark")
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/api/agent/runs/stream",
                json={"case_id": case["id"], "learner_answer": case["gold_answer"]},
            ) as response:
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
                events = [json.loads(line) for line in response.iter_lines() if line]
        stage_names = [event["stage"]["node"] for event in events if event["event"] == "stage"]
        self.assertEqual(stage_names, ["Plan", "Act", "Observe", "Verify", "Memory"])
        self.assertEqual(events[-1]["event"], "final")
        self.assertEqual(events[-1]["run"]["case_id"], case["id"])

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
            self.assertEqual(payload["metric_version"], "portfolio-agent-eval-v2.1")
            self.assertEqual(artifact["metrics"]["case_count"], 5)
            self.assertEqual(artifact["metrics"]["task_completion_rate"], 1.0)
            self.assertEqual(artifact["metrics"]["tool_selection_accuracy"], 1.0)
            self.assertEqual(artifact["metrics"]["structured_output_rate"], 1.0)
            self.assertGreaterEqual(artifact["metrics"]["retrieval_recall_at_3"], 0.8)
            self.assertEqual(artifact["metrics"]["recovery_rate"], 1.0)
            self.assertEqual(artifact["metrics"]["checkpoint_replay_rate"], 1.0)
            self.assertTrue((Path(directory) / "latest.md").exists())


if __name__ == "__main__":
    unittest.main()
