"""Runtime-only study state for the portfolio case question bank.

The versioned case pack is immutable. Attempts, favorites, wrong-case state,
review scheduling and adaptive recommendations live under backend/runtime/data
and can be reset without touching repository seeds.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from app.core.config import SAFETY_NOTICE
from app.services.data_store import read_json, write_json


STATE_FILE = "portfolio_study_state.json"


class PortfolioStudyService:
    """Small deterministic learning-state engine for the five-case demo bank."""

    def __init__(self) -> None:
        self._lock = RLock()

    def snapshot(self, cases: list[dict[str, Any]], learner_id: str = "demo_learner") -> dict[str, Any]:
        learner_key = self._learner_key(learner_id)
        with self._lock:
            state = self._read_state()
            learner = self._learner_state(state, learner_key)
            return self._build_snapshot(cases, learner_key, learner)

    def set_favorite(
        self,
        cases: list[dict[str, Any]],
        case_id: str,
        favorited: bool,
        learner_id: str = "demo_learner",
    ) -> dict[str, Any]:
        self._require_case(cases, case_id)
        learner_key = self._learner_key(learner_id)
        with self._lock:
            state = self._read_state()
            learner = self._learner_state(state, learner_key)
            favorites = [item for item in learner["favorite_case_ids"] if item != case_id]
            if favorited:
                favorites.insert(0, case_id)
            learner["favorite_case_ids"] = favorites
            learner["updated_at"] = self._now().isoformat()
            self._write_state(state)
            snapshot = self._build_snapshot(cases, learner_key, learner)
            return {
                "case_id": case_id,
                "favorited": favorited,
                "favorite_case_ids": snapshot["favorite_case_ids"],
                "summary": snapshot["summary"],
                "safety_notice": SAFETY_NOTICE,
            }

    def record_attempt(
        self,
        cases: list[dict[str, Any]],
        case: dict[str, Any],
        *,
        learner_id: str,
        score: int,
        matched_fact_ids: list[str],
        missed_fact_ids: list[str],
        source_run_id: str,
    ) -> dict[str, Any]:
        """Commit one scored Agent run and return the observable memory delta."""
        learner_key = self._learner_key(learner_id)
        bounded_score = max(0, min(100, int(score)))
        now = self._now()
        with self._lock:
            state = self._read_state()
            learner = self._learner_state(state, learner_key)
            progress = learner["case_progress"].setdefault(case["id"], self._empty_progress())
            dimension_before = dict(learner["dimension_mastery"])

            progress["attempt_count"] += 1
            progress["last_score"] = bounded_score
            progress["best_score"] = max(int(progress.get("best_score", 0)), bounded_score)
            progress["completed"] = True
            progress["last_attempt_at"] = now.isoformat()
            progress["source_run_id"] = source_run_id
            progress["missed_fact_ids"] = list(dict.fromkeys(missed_fact_ids))
            progress["last_matched_fact_ids"] = list(dict.fromkeys(matched_fact_ids))

            was_wrong = bool(progress.get("is_wrong"))
            if missed_fact_ids:
                progress["is_wrong"] = True
                progress["wrong_since"] = progress.get("wrong_since") or now.isoformat()
                progress["resolved_at"] = None
            elif was_wrong:
                progress["is_wrong"] = False
                progress["resolved_at"] = now.isoformat()

            previous_interval = int(progress.get("review_interval_days", 0))
            interval_days = self._next_interval_days(bounded_score, previous_interval)
            progress["review_interval_days"] = interval_days
            progress["review_due_at"] = (now + timedelta(days=interval_days)).isoformat()
            progress["review_stage"] = self._review_stage(interval_days)

            dimension_deltas = self._update_dimension_mastery(
                learner, case, set(matched_fact_ids), dimension_before
            )
            attempt = {
                "attempt_id": f"attempt_{source_run_id}",
                "source_run_id": source_run_id,
                "case_id": case["id"],
                "case_title": case["title"],
                "score": bounded_score,
                "matched_fact_ids": list(dict.fromkeys(matched_fact_ids)),
                "missed_fact_ids": list(dict.fromkeys(missed_fact_ids)),
                "completed_at": now.isoformat(),
            }
            learner["attempts"] = [attempt, *learner["attempts"]][:100]
            learner["updated_at"] = now.isoformat()
            self._write_state(state)
            adaptive = self._adaptive_recommendation(cases, learner, now)

        return {
            "learner_id": learner_key,
            "mode": "runtime_study_commit",
            "committed": True,
            "source_run_id": source_run_id,
            "case_id": case["id"],
            "score": bounded_score,
            "missed_fact_ids": list(dict.fromkeys(missed_fact_ids)),
            "dimension_deltas": dimension_deltas,
            "review_schedule": {
                "interval_days": interval_days,
                "due_at": progress["review_due_at"],
                "stage": progress["review_stage"],
            },
            "adaptive_recommendation": adaptive,
            "reason": "本次结果仅写入可重置的演示学习状态，未修改版本库 seed。",
        }

    def _build_snapshot(
        self, cases: list[dict[str, Any]], learner_id: str, learner: dict[str, Any]
    ) -> dict[str, Any]:
        now = self._now()
        favorites = set(learner["favorite_case_ids"])
        items: list[dict[str, Any]] = []
        review_queue: list[dict[str, Any]] = []
        wrong_book: list[dict[str, Any]] = []
        for case in cases:
            progress = learner["case_progress"].get(case["id"], self._empty_progress())
            due_at = self._parse_time(progress.get("review_due_at"))
            review_due = bool(progress["completed"] and (progress["is_wrong"] or due_at is None or due_at <= now))
            item = {
                "id": case["id"],
                "title": case["title"],
                "source_dataset": case.get("source_dataset", ""),
                "source_type": case.get("source_type", "公开教学样例"),
                "body_part": case.get("body_part"),
                "difficulty": case.get("difficulty"),
                "image_url": case.get("image_url"),
                "prompt": case.get("prompt"),
                "fact_count": len(case.get("facts", [])),
                "favorite": case["id"] in favorites,
                "favorited": case["id"] in favorites,
                "completed": bool(progress["completed"]),
                "best_score": int(progress["best_score"]) if progress["completed"] else None,
                "wrong": bool(progress["is_wrong"]),
                "last_practiced_at": progress.get("last_attempt_at"),
                "tags": list(dict.fromkeys(fact["dimension"] for fact in case.get("facts", []))),
                "estimated_minutes": 5,
                "progress": {
                    **progress,
                    "review_due": review_due,
                    "mastery": self._case_mastery(case, learner),
                },
            }
            items.append(item)
            if review_due:
                review_queue.append({
                    **item,
                    "queue_reason": "错题待巩固" if progress["is_wrong"] else "间隔复习到期",
                })
            if progress["is_wrong"]:
                wrong_book.append({
                    **item,
                    "missing_fact_labels": [
                        fact["label"] for fact in case.get("facts", [])
                        if fact["id"] in set(progress.get("missed_fact_ids", []))
                    ],
                })

        adaptive = self._adaptive_recommendation(cases, learner, now)
        by_id = {item["id"]: item for item in items}
        today_task = by_id.get(adaptive["case_id"]) if adaptive else (items[0] if items else None)
        completed = [item for item in items if item["progress"]["completed"]]
        best_scores = [int(item["progress"]["best_score"]) for item in completed]
        review_queue.sort(key=lambda item: (not item["progress"]["is_wrong"], item["progress"].get("review_due_at") or ""))
        wrong_book.sort(key=lambda item: item["progress"].get("last_attempt_at") or "", reverse=True)
        plan_items = self._today_plan(items, review_queue, adaptive)
        attempts_today = [
            attempt for attempt in learner["attempts"]
            if (parsed := self._parse_time(attempt.get("completed_at"))) and parsed.date() == now.date()
        ]
        completed_case_ids_today = {
            str(attempt.get("case_id")) for attempt in attempts_today if attempt.get("case_id")
        }
        all_attempt_scores = [int(attempt.get("score", 0)) for attempt in learner["attempts"]]
        return {
            "version": "portfolio-study-v2.1",
            "learner_id": learner_id,
            "today_task": {
                "case": today_task,
                "recommendation": adaptive,
            } if today_task else None,
            "adaptive_recommendation": adaptive,
            "summary": {
                "total_cases": len(items),
                "completed_count": len(completed),
                "completion_rate": round(len(completed) / max(len(items), 1), 4),
                "average_best_score": round(sum(best_scores) / max(len(best_scores), 1), 1),
                "wrong_count": len(wrong_book),
                "favorite_count": len(favorites),
                "due_review_count": len(review_queue),
                "attempt_count": len(learner["attempts"]),
            },
            # Presentation-oriented aliases consumed by the v2.1 Study Center.
            "learner": {
                "completed_today": len(completed_case_ids_today),
                "daily_target": 3,
                "streak_days": self._streak_days(learner["attempts"], now),
                "total_completed": len(completed),
                "accuracy": round(sum(all_attempt_scores) / len(all_attempt_scores) / 100, 4) if all_attempt_scores else None,
                "wrong_count": len(wrong_book),
                "favorite_count": len(favorites),
            },
            "today_plan": {
                "title": "今日自适应训练",
                "reason": adaptive["reason"] if adaptive else "当前题库已完成，可按收藏或间隔复习继续巩固。",
                "generated_by": "Training Agent",
                "items": plan_items,
            },
            "library": {
                "items": items,
                "body_parts": list(dict.fromkeys(str(item["body_part"]) for item in items if item["body_part"])),
            },
            "continue_case_id": adaptive["case_id"] if adaptive else (items[0]["id"] if items else None),
            "source": "backend",
            "dimension_mastery": learner["dimension_mastery"],
            "favorite_case_ids": learner["favorite_case_ids"],
            "cases": items,
            "review_queue": review_queue,
            "wrong_book": wrong_book,
            "recent_attempts": learner["attempts"][:10],
            "runtime_isolated": True,
            "updated_at": learner.get("updated_at"),
            "safety_notice": SAFETY_NOTICE,
        }

    def _today_plan(
        self,
        items: list[dict[str, Any]],
        review_queue: list[dict[str, Any]],
        adaptive: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        by_id = {item["id"]: item for item in items}
        selected_ids: list[str] = []
        if adaptive:
            selected_ids.append(adaptive["case_id"])
        selected_ids.extend(item["id"] for item in review_queue)
        selected_ids.extend(item["id"] for item in items if not item["completed"])
        selected_ids.extend(item["id"] for item in items if item["favorited"])
        selected_ids.extend(item["id"] for item in items)
        plan = []
        for case_id in dict.fromkeys(selected_ids):
            item = dict(by_id[case_id])
            if adaptive and case_id == adaptive["case_id"]:
                item["recommendation_reason"] = adaptive["reason"]
            elif item["wrong"]:
                item["recommendation_reason"] = "错题自动回收：优先补齐上次遗漏的事实点。"
            elif not item["completed"]:
                item["recommendation_reason"] = "未完成病例：补齐题库训练覆盖。"
            else:
                item["recommendation_reason"] = "按间隔复习节奏巩固已完成病例。"
            plan.append(item)
            if len(plan) >= 3:
                break
        return plan

    def _streak_days(self, attempts: list[dict[str, Any]], now: datetime) -> int:
        dates = {
            parsed.date()
            for attempt in attempts
            if (parsed := self._parse_time(attempt.get("completed_at")))
        }
        if not dates:
            return 0
        cursor = now.date()
        if cursor not in dates:
            cursor -= timedelta(days=1)
        streak = 0
        while cursor in dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def _adaptive_recommendation(
        self, cases: list[dict[str, Any]], learner: dict[str, Any], now: datetime
    ) -> dict[str, Any] | None:
        if not cases:
            return None
        progress_by_case = learner["case_progress"]
        uncompleted = [case for case in cases if not progress_by_case.get(case["id"], {}).get("completed")]
        if uncompleted:
            weakest_dimension = self._weakest_dimension(learner)
            targeted = [
                case for case in uncompleted
                if any(fact.get("dimension") == weakest_dimension for fact in case.get("facts", []))
            ]
            selected = (targeted or uncompleted)[0]
            return {
                "case_id": selected["id"],
                "case_title": selected["title"],
                "strategy": "unfinished_first",
                "priority": "high",
                "weakest_dimension": weakest_dimension,
                "reason": f"优先完成未作答病例，并覆盖当前最低掌握维度“{weakest_dimension}”。",
            }

        ranked: list[tuple[int, int, str, dict[str, Any]]] = []
        for case in cases:
            progress = progress_by_case.get(case["id"], self._empty_progress())
            due_at = self._parse_time(progress.get("review_due_at"))
            due_priority = 0 if progress.get("is_wrong") else 1 if due_at is None or due_at <= now else 2
            ranked.append((due_priority, self._case_mastery(case, learner), progress.get("last_attempt_at") or "", case))
        _, mastery, _, selected = sorted(ranked, key=lambda row: (row[0], row[1], row[2]))[0]
        weakest_dimension = self._weakest_case_dimension(selected, learner)
        return {
            "case_id": selected["id"],
            "case_title": selected["title"],
            "strategy": "weakness_and_spaced_review",
            "priority": "high" if progress_by_case[selected["id"]].get("is_wrong") else "normal",
            "weakest_dimension": weakest_dimension,
            "mastery": mastery,
            "reason": f"根据错题状态、复习到期时间与最低掌握维度“{weakest_dimension}”动态推荐。",
        }

    def _update_dimension_mastery(
        self,
        learner: dict[str, Any],
        case: dict[str, Any],
        matched: set[str],
        before: dict[str, int],
    ) -> list[dict[str, Any]]:
        deltas = []
        dimensions = dict.fromkeys(fact["dimension"] for fact in case.get("facts", []))
        for dimension in dimensions:
            facts = [fact for fact in case["facts"] if fact["dimension"] == dimension]
            covered = sum(fact["id"] in matched for fact in facts)
            observed_score = round(covered / max(len(facts), 1) * 100)
            old = int(learner["dimension_mastery"].get(dimension, 70))
            new = max(0, min(100, round(old * 0.7 + observed_score * 0.3)))
            learner["dimension_mastery"][dimension] = new
            deltas.append({
                "dimension": dimension,
                "before": int(before.get(dimension, old)),
                "delta": new - old,
                "after_preview": new,
                "after": new,
                "reason": f"本次覆盖 {covered}/{len(facts)} 条事实，按指数滑动更新掌握度。",
            })
        return deltas

    def _case_mastery(self, case: dict[str, Any], learner: dict[str, Any]) -> int:
        dimensions = list(dict.fromkeys(fact["dimension"] for fact in case.get("facts", [])))
        if not dimensions:
            return 70
        return round(sum(int(learner["dimension_mastery"].get(item, 70)) for item in dimensions) / len(dimensions))

    def _weakest_case_dimension(self, case: dict[str, Any], learner: dict[str, Any]) -> str:
        dimensions = list(dict.fromkeys(fact["dimension"] for fact in case.get("facts", [])))
        if not dimensions:
            return "综合观察"
        return min(dimensions, key=lambda item: (int(learner["dimension_mastery"].get(item, 70)), item))

    def _weakest_dimension(self, learner: dict[str, Any]) -> str:
        scores = learner["dimension_mastery"]
        return min(scores, key=lambda item: (int(scores[item]), item)) if scores else "部位定位"

    def _read_state(self) -> dict[str, Any]:
        try:
            payload = read_json(STATE_FILE)
        except (FileNotFoundError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("version", "portfolio-study-v2.1")
        payload.setdefault("learners", {})
        return payload

    def _write_state(self, state: dict[str, Any]) -> None:
        write_json(STATE_FILE, state)

    def _learner_state(self, state: dict[str, Any], learner_id: str) -> dict[str, Any]:
        learner = state["learners"].setdefault(learner_id, {})
        learner.setdefault("favorite_case_ids", [])
        learner.setdefault("attempts", [])
        learner.setdefault("case_progress", {})
        learner.setdefault("dimension_mastery", {})
        learner.setdefault("updated_at", None)
        return learner

    def _require_case(self, cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
        for case in cases:
            if case["id"] == case_id:
                return case
        raise KeyError(f"Portfolio case not found: {case_id}")

    def _learner_key(self, learner_id: str) -> str:
        value = str(learner_id).strip()
        if not value or len(value) > 64:
            raise ValueError("learner_id must contain 1-64 characters")
        return value

    def _empty_progress(self) -> dict[str, Any]:
        return {
            "attempt_count": 0,
            "last_score": 0,
            "best_score": 0,
            "completed": False,
            "is_wrong": False,
            "wrong_since": None,
            "resolved_at": None,
            "last_attempt_at": None,
            "source_run_id": None,
            "missed_fact_ids": [],
            "last_matched_fact_ids": [],
            "review_interval_days": 0,
            "review_due_at": None,
            "review_stage": "new",
        }

    def _next_interval_days(self, score: int, previous: int) -> int:
        if score < 70:
            return 0
        if score < 90:
            return 1
        return 1 if previous <= 0 else 3 if previous <= 1 else min(previous * 2, 30)

    def _review_stage(self, interval_days: int) -> str:
        if interval_days <= 0:
            return "relearn_now"
        if interval_days == 1:
            return "review_tomorrow"
        return "spaced_review"

    def _parse_time(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


portfolio_study_service = PortfolioStudyService()
