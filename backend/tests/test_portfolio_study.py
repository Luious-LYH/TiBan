import hashlib
import unittest

from fastapi.testclient import TestClient

from app.core.config import DATA_DIR, RUNTIME_DATA_DIR
from app.main import app
from app.services.portfolio_agent_runtime import portfolio_agent_runtime
from app.services.portfolio_eval_service import portfolio_eval_service


class PortfolioStudyTests(unittest.TestCase):
    def setUp(self):
        self.state_path = RUNTIME_DATA_DIR / "portfolio_study_state.json"
        self.previous_state = self.state_path.read_bytes() if self.state_path.exists() else None
        self.state_path.unlink(missing_ok=True)

    def tearDown(self):
        self.state_path.unlink(missing_ok=True)
        if self.previous_state is not None:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_bytes(self.previous_state)

    def test_initial_bank_exposes_today_task_and_unfinished_recommendation(self):
        with TestClient(app) as client:
            response = client.get("/api/portfolio/study")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total_cases"], 5)
        self.assertEqual(payload["summary"]["completed_count"], 0)
        self.assertEqual(payload["adaptive_recommendation"]["strategy"], "unfinished_first")
        self.assertEqual(payload["today_task"]["case"]["id"], payload["adaptive_recommendation"]["case_id"])
        self.assertTrue(payload["runtime_isolated"])

    def test_committed_agent_run_records_wrong_case_review_and_source_run(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/agent/runs",
                json={
                    "case_id": "case_esophagus_landmark",
                    "learner_answer": "可见 Z 线，建议医生复核。",
                    "commit_memory": True,
                },
            )
            self.assertEqual(response.status_code, 200)
            run = response.json()
            study = client.get("/api/portfolio/study").json()

        self.assertTrue(run["memory_delta"]["committed"])
        self.assertEqual(run["memory_delta"]["source_run_id"], run["run_id"])
        self.assertGreater(len(run["memory_delta"]["missed_fact_ids"]), 0)
        self.assertEqual(study["summary"]["attempt_count"], 1)
        self.assertEqual(study["summary"]["wrong_count"], 1)
        self.assertEqual(study["summary"]["due_review_count"], 1)
        self.assertEqual(study["wrong_book"][0]["progress"]["source_run_id"], run["run_id"])
        self.assertEqual(study["recent_attempts"][0]["source_run_id"], run["run_id"])
        self.assertTrue(self.state_path.exists())
        self.assertFalse((DATA_DIR / "portfolio_study_state.json").exists())

    def test_full_retry_resolves_wrong_case_and_advances_interval(self):
        case = portfolio_agent_runtime.get_case("case_esophagus_landmark")
        with TestClient(app) as client:
            client.post(
                "/api/agent/runs",
                json={"case_id": case["id"], "learner_answer": "Z 线，医生复核。", "commit_memory": True},
            )
            second = client.post(
                "/api/agent/runs",
                json={"case_id": case["id"], "learner_answer": case["gold_answer"], "commit_memory": True},
            ).json()
            study = client.get("/api/portfolio/study").json()

        self.assertTrue(second["memory_delta"]["committed"])
        self.assertEqual(second["memory_delta"]["review_schedule"]["interval_days"], 1)
        self.assertEqual(study["summary"]["wrong_count"], 0)
        progress = next(item["progress"] for item in study["cases"] if item["id"] == case["id"])
        self.assertEqual(progress["attempt_count"], 2)
        self.assertEqual(study["learner"]["completed_today"], 1)
        self.assertFalse(progress["is_wrong"])
        self.assertIsNotNone(progress["resolved_at"])

    def test_favorite_toggle_and_demo_reset_are_runtime_only(self):
        seed_hash = hashlib.sha256((DATA_DIR / "portfolio_cases.json").read_bytes()).hexdigest()
        with TestClient(app) as client:
            favorite = client.post(
                "/api/portfolio/study/favorites/case_capsule_anatomy",
                json={"favorited": True},
            )
            self.assertEqual(favorite.status_code, 200)
            self.assertIn("case_capsule_anatomy", favorite.json()["favorite_case_ids"])
            self.assertTrue(self.state_path.exists())
            reset = client.post("/api/demo/reset")
            self.assertEqual(reset.status_code, 200)
            self.assertIn("portfolio_study_state.json", reset.json()["restored"])
            clean = client.get("/api/portfolio/study").json()

        self.assertFalse(self.state_path.exists())
        self.assertEqual(clean["summary"]["attempt_count"], 0)
        self.assertEqual(clean["summary"]["favorite_count"], 0)
        self.assertEqual(hashlib.sha256((DATA_DIR / "portfolio_cases.json").read_bytes()).hexdigest(), seed_hash)

    def test_default_eval_and_checkpoint_replay_do_not_commit(self):
        case = portfolio_agent_runtime.get_case("case_capsule_anatomy")
        source = portfolio_agent_runtime.run(case["id"], case["gold_answer"], commit_memory=True)
        replay = portfolio_agent_runtime.replay(source["run_id"])
        self.assertFalse(replay["memory_delta"]["committed"])
        with TestClient(app) as client:
            before = client.get("/api/portfolio/study").json()["summary"]["attempt_count"]
            plain = portfolio_agent_runtime.run(case["id"], case["gold_answer"])
            portfolio_eval_service.run()
            after = client.get("/api/portfolio/study").json()["summary"]["attempt_count"]
        self.assertFalse(plain["memory_delta"]["committed"])
        self.assertEqual(before, 1)
        self.assertEqual(after, 1)


if __name__ == "__main__":
    unittest.main()
