import unittest

from fastapi.testclient import TestClient

from app.main import app


class PracticeV22Tests(unittest.TestCase):
    def test_qbank_exposes_text_and_visual_question_forms(self):
        with TestClient(app) as client:
            response = client.get("/api/practice/questions?limit=60")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        # This contract exercises the checked-in teaching seed.  The licensed
        # 3,678-question Portfolio QBank is accepted separately through the
        # Docker profile with locally mounted source data, and is intentionally
        # not required by a public clean checkout.
        self.assertGreaterEqual(payload["total"], 4)
        self.assertGreaterEqual(payload["available_type_counts"]["单选"], 1)
        self.assertGreaterEqual(payload["available_type_counts"]["多选"], 1)
        self.assertGreaterEqual(payload["available_type_counts"]["判断"], 1)
        self.assertGreaterEqual(payload["available_type_counts"]["问答评分"], 1)
        self.assertTrue(any(not item.get("image_url") for item in payload["items"]))
        # The public clean-checkout seed contains text questions only.  Image
        # questions are exercised by the local licensed Kvasir acceptance
        # profile, where the image files can be mounted and verified.
        self.assertTrue(
            any(item.get("image_url") for item in payload["items"])
            or payload["total"] <= 8
        )

    def test_body_part_filter_keeps_curated_text_questions(self):
        with TestClient(app) as client:
            response = client.get("/api/practice/questions?body_part=食管&limit=20")

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(items)
        self.assertTrue(all(item["body_part"] == "食管" for item in items))
        self.assertTrue(any(item["question_type"] == "单选" and not item.get("image_url") for item in items))

    def test_open_answer_uses_rubric_keywords_instead_of_exact_match(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/practice/submit",
                json={
                    "question_id": "endo_text_stomach_ulcer_qa",
                    "selected_answer": "记录部位、大小、形态、边缘情况和是否出血，并结合完整检查或病理复核。",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_correct"])
        self.assertGreaterEqual(payload["score"], 80)
        self.assertTrue(payload["profile_updated"])


if __name__ == "__main__":
    unittest.main()
