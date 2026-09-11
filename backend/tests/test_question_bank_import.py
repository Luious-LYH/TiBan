from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.db.models import QuestionBankDeletionModel, QuestionBankModel, QuestionModel, SourceDocumentModel
from app.domains import build_custom_domain_id, get_domain
from app.services.question_bank_import_service import question_bank_import_service


_created_bank_ids: set[str] = set()


def test_custom_domain_ids_are_length_safe_for_long_unicode_names() -> None:
    short_name = "产品经理基础"
    long_name = "领域" * 48

    for name in (short_name, long_name):
        domain_id = build_custom_domain_id(name)
        assert domain_id.startswith("custom_")
        assert len(domain_id) <= 100
        assert get_domain(domain_id).display_name == name[:48]


@pytest.fixture(autouse=True)
def cleanup_imported_banks() -> None:
    """Keep durable-import coverage from changing other test expectations."""

    yield
    if not _created_bank_ids:
        return
    with SessionLocal() as session:
        for bank_id in _created_bank_ids:
            session.query(SourceDocumentModel).filter(SourceDocumentModel.bank_id == bank_id).delete(
                synchronize_session=False
            )
            session.query(QuestionModel).filter(QuestionModel.bank_id == bank_id).delete(
                synchronize_session=False
            )
            session.query(QuestionBankModel).filter(QuestionBankModel.bank_id == bank_id).delete(
                synchronize_session=False
            )
        session.commit()
    _created_bank_ids.clear()


def test_import_parser_accepts_json_csv_jsonl_and_markdown() -> None:
    records = [
        {"question": "Python 的列表是有序的吗？", "question_type": "单选", "options": ["是", "否"], "answer": "A"},
        {"question": "下列哪些是版本控制工具？", "question_type": "多选", "options": ["Git", "GitHub", "画图软件"], "answer": ["Git", "GitHub"]},
        {"question": "JSON 可表示嵌套对象。", "question_type": "判断", "options": ["正确", "错误"], "answer": True},
    ]
    json_result = question_bank_import_service.validate({"format": "json", "content": json.dumps(records, ensure_ascii=False)})
    assert json_result["accepted_count"] == 3
    assert json_result["rejected_count"] == 0

    mixed_json_result = question_bank_import_service.validate({
        "format": "json",
        "content": json.dumps([records[0], "not a question object"], ensure_ascii=False),
    })
    assert mixed_json_result["accepted_count"] == 1
    assert mixed_json_result["rejected_count"] == 1
    assert mixed_json_result["issues"][0]["code"] == "row_not_object"

    csv_result = question_bank_import_service.validate({"format": "csv", "content": "question,question_type,options,answer\n二进制 10 等于十进制多少？,single_choice,10|2,A"})
    assert csv_result["accepted_count"] == 1

    jsonl_result = question_bank_import_service.validate({"format": "jsonl", "content": '{"question":"RAG 会先检索资料吗？","question_type":"true_false","answer":"正确"}'})
    assert jsonl_result["accepted_count"] == 1

    markdown = (Path(__file__).resolve().parents[2] / "临时生成题库目录" / "AI岗位题库样例.md").read_text(encoding="utf-8")
    markdown_result = question_bank_import_service.validate({"format": "markdown", "content": markdown})
    assert markdown_result["accepted_count"] == 6
    assert markdown_result["rejected_count"] == 0


def test_chinese_csv_template_is_excel_safe_and_importable() -> None:
    template_path = Path(__file__).resolve().parents[2] / "临时生成题库目录" / "AI岗位题库样例.csv"
    raw = template_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

    result = question_bank_import_service.validate({
        "format": "csv",
        "content": raw.decode("utf-8-sig"),
    })
    assert result["accepted_count"] == 6
    assert result["rejected_count"] == 0
    assert result["summary"]["question_type_counts"] == {
        "single_choice": 3,
        "multiple_choice": 1,
        "true_false": 2,
    }


def test_csv_bom_and_separate_option_columns_are_normalized() -> None:
    content = "\ufeff题干,题型,选项A,选项B,选项C,正确答案\n向量数据库通常用于什么？,单选,存储向量,渲染页面,发送邮件,存储向量\n"

    result = question_bank_import_service.validate({"format": "csv", "content": content})

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 0
    assert [option["text"] for option in result["items"][0]["options"]] == ["存储向量", "渲染页面", "发送邮件"]


def test_large_preview_returns_every_validated_question() -> None:
    records = []
    for index in range(100):
        records.append({
            "question": f"批量预览第 {index + 1} 题。",
            "question_type": "判断",
            "answer": "正确" if index % 2 == 0 else "错误",
        })

    result = question_bank_import_service.validate({
        "format": "json",
        "content": json.dumps(records, ensure_ascii=False),
        "source_name": "100题预览回归样例",
    })

    assert result["accepted_count"] == 100
    assert result["rejected_count"] == 0
    assert len(result["items"]) == 100
    assert result["items"][0]["question"] == "批量预览第 1 题。"
    assert result["items"][-1]["question"] == "批量预览第 100 题。"


def test_create_and_append_question_bank_are_durable_and_idempotent() -> None:
    content = "\n".join([
        json.dumps({"question": "导入链路会写入数据库吗？", "question_type": "单选", "options": ["会", "不会"], "answer": "会"}, ensure_ascii=False),
        json.dumps({"question": "追加题目会删除原题吗？", "question_type": "判断", "answer": "否"}, ensure_ascii=False),
    ])
    created = question_bank_import_service.import_questions({"format": "jsonl", "content": content, "mode": "create_bank", "bank_name": "导入链路回归题库", "source_name": "本地回归样例", "domain_id": "general_science"})
    _created_bank_ids.add(created["bank_id"])
    assert created["imported_count"] == 2
    assert created["question_count"] == 2

    with SessionLocal() as session:
        bank = session.get(QuestionBankModel, created["bank_id"])
        questions = list(session.query(QuestionModel).filter(QuestionModel.bank_id == created["bank_id"]).all())
        source = session.get(SourceDocumentModel, created["source_document_id"])
        assert bank is not None and bank.question_count == 2
        assert len(questions) == 2
        assert all(question.case_summary == "" for question in questions)
        assert source is not None and source.bank_id == created["bank_id"]

    duplicate = question_bank_import_service.import_questions({"format": "jsonl", "content": content, "mode": "append_questions", "target_bank_id": created["bank_id"], "domain_id": "general_science"})
    assert duplicate["imported_count"] == 0
    assert duplicate["duplicate_count"] == 2
    assert duplicate["question_count"] == 2

    extra = question_bank_import_service.import_questions({"format": "jsonl", "content": json.dumps({"question": "追加后题库题量会更新吗？", "question_type": "单选", "options": ["会", "不会"], "answer": "A"}, ensure_ascii=False), "mode": "append_questions", "target_bank_id": created["bank_id"], "domain_id": "general_science"})
    assert extra["imported_count"] == 1
    assert extra["question_count"] == 3


def test_invalid_rows_are_reported_and_valid_rows_can_be_imported() -> None:
    content = "\n".join([
        json.dumps({"question": "完整题目", "question_type": "单选", "options": ["A", "B"], "answer": "A"}, ensure_ascii=False),
        json.dumps({"question": "缺答案题目", "question_type": "单选", "options": ["A", "B"]}, ensure_ascii=False),
    ])
    result = question_bank_import_service.import_questions({"format": "jsonl", "content": content, "mode": "create_bank", "bank_name": "部分有效回归题库", "domain_id": "general_science"})
    _created_bank_ids.add(result["bank_id"])
    assert result["imported_count"] == 1
    assert result["rejected_count"] == 1
    assert result["status"] == "partial"
    assert result["issues"][0]["code"] == "missing_answer"


def test_each_supported_format_can_be_persisted() -> None:
    records = {
        "json": (
            "["
            '{"question":"JSON 导入题目","question_type":"single_choice","options":["对","错"],"answer":"A"}'
            "]"
        ),
        "jsonl": '{"question":"JSONL 导入题目","question_type":"判断","answer":"正确"}',
        "csv": "question,question_type,options,answer\nCSV 导入题目,single_choice,对|错,A\n",
        "markdown": "## Markdown 导入题目\n题型: 判断\n答案: 正确\n",
    }
    for fmt, content in records.items():
        result = question_bank_import_service.import_questions({
            "format": fmt,
            "content": content,
            "mode": "create_bank",
            "bank_name": f"{fmt} 格式回归题库",
            "source_name": f"{fmt} 格式样例",
            "domain_id": "general_science",
        })
        _created_bank_ids.add(result["bank_id"])
        assert result["imported_count"] == 1
        assert result["question_count"] == 1


def test_import_http_flow_creates_lists_appends_and_deduplicates() -> None:
    content = json.dumps(
        {
            "question": "HTTP 导入后能在题库列表中看到吗？",
            "question_type": "单选",
            "options": ["能", "不能"],
            "answer": "A",
        },
        ensure_ascii=False,
    )
    with TestClient(app) as client:
        validation = client.post(
            "/api/question-banks/import/validate",
            json={"format": "json", "content": f"[{content}]", "source_name": "HTTP 回归样例"},
        )
        assert validation.status_code == 200
        assert validation.json()["accepted_count"] == 1

        created_response = client.post(
            "/api/v3/question-banks/import",
            json={
                "format": "json",
                "content": f"[{content}]",
                "mode": "create_bank",
                "bank_name": "HTTP 导入回归题库",
                "source_name": "HTTP 回归样例",
                "domain_id": "general_science",
            },
        )
        assert created_response.status_code == 200
        created = created_response.json()
        _created_bank_ids.add(created["bank_id"])
        assert created["imported_count"] == 1
        assert created["question_count"] == 1

        banks = client.get("/api/v3/question-banks", params={"domain_id": "general_science"})
        assert banks.status_code == 200
        assert any(item["bank_id"] == created["bank_id"] for item in banks.json()["items"])

        questions = client.get(f"/api/v3/question-banks/{created['bank_id']}/questions")
        assert questions.status_code == 200
        assert questions.json()["total"] == 1
        assert questions.json()["items"][0]["question_type"] == "single_choice"

        searched_questions = client.get(
            f"/api/v3/question-banks/{created['bank_id']}/questions",
            params={"search": "HTTP 导入后"},
        )
        assert searched_questions.status_code == 200
        assert searched_questions.json()["total"] == 1
        assert searched_questions.json()["items"][0]["question_id"] == questions.json()["items"][0]["question_id"]

        appended = client.post(
            "/api/v3/question-banks/import",
            json={
                "format": "json",
                "content": f"[{content}]",
                "mode": "append_questions",
                "target_bank_id": created["bank_id"],
                "domain_id": "general_science",
            },
        )
        assert appended.status_code == 200
        assert appended.json()["imported_count"] == 0
        assert appended.json()["duplicate_count"] == 1
        assert appended.json()["question_count"] == 1


def test_saved_bank_and_question_can_be_edited_through_authoring_contract() -> None:
    content = json.dumps({
        "question": "哪个组件负责向量检索？",
        "question_type": "单选",
        "options": ["Embedding 模型", "CSS 样式", "浏览器缓存"],
        "answer": "A",
        "explanation": "向量检索依赖 Embedding 表示。",
    }, ensure_ascii=False)
    with TestClient(app) as client:
        created = client.post("/api/v3/question-banks/import", json={
            "format": "json",
            "content": f"[{content}]",
            "mode": "create_bank",
            "bank_name": "可编辑 AI 题库",
            "bank_description": "初始说明",
            "domain_id": "general_science",
        })
        assert created.status_code == 200
        bank_id = created.json()["bank_id"]
        _created_bank_ids.add(bank_id)

        renamed = client.patch(f"/api/v3/question-banks/{bank_id}", json={
            "name": "可编辑 AI 算法题库",
            "description": "更新后的说明",
        })
        assert renamed.status_code == 200
        assert renamed.json()["item"]["name"] == "可编辑 AI 算法题库"

        question_id = client.get(f"/api/v3/question-banks/{bank_id}/questions").json()["items"][0]["question_id"]
        edit = client.get(f"/api/v3/question-banks/{bank_id}/questions/{question_id}/edit")
        assert edit.status_code == 200
        assert edit.json()["item"]["answer"] == "A"
        updated = client.patch(f"/api/v3/question-banks/{bank_id}/questions/{question_id}/edit", json={
            "title": "检索组件识别",
            "stem": "在 RAG 系统中，哪个组件负责把文本转换为向量？",
            "question_type": "single_choice",
            "options": [
                {"id": "opt_0", "text": "Embedding 模型"},
                {"id": "opt_1", "text": "CSS 样式"},
                {"id": "opt_2", "text": "浏览器缓存"},
            ],
            "answer": "A",
            "explanation": "Embedding 模型把文本编码成可检索的向量表示。",
            "difficulty": "medium",
            "tags": ["RAG", "Embedding"],
            "body_part": "AI 工程",
            "subject": "大模型应用",
            "topic": "向量检索",
            "task": "概念理解",
        })
        assert updated.status_code == 200
        assert updated.json()["item"]["stem"].startswith("在 RAG 系统中")


def test_review_batch_persists_decisions_and_publishes_only_approved_questions() -> None:
    content = "\n".join([
        json.dumps({"question": "审核批次会保存吗？", "question_type": "单选", "options": ["会", "不会"], "answer": "A", "explanation": "审核状态写入数据库。"}, ensure_ascii=False),
        json.dumps({"question": "未审核题目会直接入正式题库吗？", "question_type": "判断", "answer": "错误"}, ensure_ascii=False),
    ])
    with TestClient(app) as client:
        created = client.post("/api/v3/factory/import-batches", json={
            "format": "jsonl",
            "content": content,
            "domain_id": "general_science",
            "source_name": "持久化审核回归样例",
            "file_name": "review.jsonl",
        })
        assert created.status_code == 200
        batch = created.json()["item"]
        assert batch["total_count"] == 2
        assert batch["pending_count"] == 2
        assert batch["items"][0]["status"] == "pending"

        approved = client.patch(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/drafts/{batch['items'][0]['draft_id']}",
            json={"status": "approved"},
        )
        assert approved.status_code == 200
        assert approved.json()["item"]["approved_count"] == 1
        assert approved.json()["item"]["pending_count"] == 1

        reopened = client.get(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert reopened.status_code == 200
        assert reopened.json()["item"]["items"][0]["status"] == "approved"

        published = client.post(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/publish",
            json={"mode": "create_bank", "bank_name": "持久化审核发布题库", "bank_description": "只包含审核通过题目"},
        )
        assert published.status_code == 200
        result = published.json()["item"]
        assert result["imported_count"] == 1
        assert result["pending_count"] == 1
        bank_id = result["bank_id"]
        _created_bank_ids.add(bank_id)

        approved_later = client.patch(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/drafts/{batch['items'][1]['draft_id']}",
            json={"status": "approved"},
        )
        assert approved_later.status_code == 200
        assert approved_later.json()["item"]["approved_count"] == 1

        published_later = client.post(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/publish",
            json={"mode": "create_bank", "bank_name": "本次调用不会新建题库"},
        )
        assert published_later.status_code == 200
        assert published_later.json()["item"]["imported_count"] == 1
        assert published_later.json()["item"]["published_count"] == 2
        assert published_later.json()["item"]["pending_count"] == 0

        questions = client.get(f"/api/v3/question-banks/{bank_id}/questions")
        assert questions.status_code == 200
        assert questions.json()["total"] == 2
        assert {item["question_type"] for item in questions.json()["items"]} == {"single_choice", "true_false"}

        deleted_batch = client.delete(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert deleted_batch.status_code == 200
        assert deleted_batch.json()["deleted"] is True


def test_review_batch_keeps_parse_issues_after_reopening() -> None:
    valid = json.dumps(
        {"question": "问题提示会持久化吗？", "question_type": "判断", "answer": "正确"},
        ensure_ascii=False,
    )
    invalid = json.dumps(
        {"question": "缺少答案的题目", "question_type": "判断"},
        ensure_ascii=False,
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v3/factory/import-batches",
            json={
                "format": "jsonl",
                "content": f"{valid}\n{invalid}",
                "domain_id": "general_science",
                "source_name": "持久化问题回归样例",
            },
        )
        assert created.status_code == 200
        batch = created.json()["item"]
        assert batch["issues"][0]["code"] == "missing_answer"

        reopened = client.get(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert reopened.status_code == 200
        assert reopened.json()["item"]["issues"][0]["code"] == "missing_answer"

        deleted = client.delete(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert deleted.status_code == 200


def test_question_bank_order_requires_complete_catalog_and_survives_reload() -> None:
    created_ids: list[str] = []
    for index in range(2):
        result = question_bank_import_service.import_questions({
            "format": "json",
            "content": json.dumps({
                "question": f"排序回归题目 {index}",
                "question_type": "判断",
                "answer": "正确",
            }, ensure_ascii=False),
            "mode": "create_bank",
            "bank_name": f"排序回归题库 {index}",
            "domain_id": "endoscopy",
        })
        created_ids.append(result["bank_id"])
        _created_bank_ids.add(result["bank_id"])

    with TestClient(app) as client:
        current = client.get("/api/v3/question-banks").json()["items"]
        current_ids = [item["bank_id"] for item in current]
        assert set(created_ids).issubset(current_ids)

        partial = client.put("/api/v3/question-banks/order", json={"bank_ids": current_ids[:-1]})
        assert partial.status_code == 422
        assert "全部题库" in partial.json()["detail"]

        requested = list(reversed(current_ids))
        reordered = client.put("/api/v3/question-banks/order", json={"bank_ids": requested})
        assert reordered.status_code == 200
        assert reordered.json()["bank_ids"] == requested

        reloaded = client.get("/api/v3/question-banks").json()["items"]
        assert [item["bank_id"] for item in reloaded] == requested


def test_any_question_bank_can_be_deleted_and_is_tombstoned() -> None:
    bank_id = "bank-delete-contract"
    with SessionLocal() as session:
        session.add(QuestionBankModel(
            bank_id=bank_id,
            domain_id="general_science",
            name="删除契约回归题库",
            description="用于验证题库删除契约。",
            version="test-v1",
            status="published",
            question_count=0,
            question_type_counts={},
            modality_counts={},
            body_parts=[],
        ))
        session.commit()
    with TestClient(app) as client:
        response = client.delete(f"/api/v3/question-banks/{bank_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
    with SessionLocal() as session:
        assert session.get(QuestionBankModel, bank_id) is None
        assert session.get(QuestionBankDeletionModel, bank_id) is not None


def test_custom_domain_is_stored_and_uses_generic_learning_policy() -> None:
    result = question_bank_import_service.import_questions({
        "format": "json",
        "content": json.dumps({"question": "自定义领域题目", "question_type": "判断", "answer": "正确"}, ensure_ascii=False),
        "mode": "create_bank",
        "bank_name": "自定义领域回归题库",
        "domain_id": "__custom__",
        "custom_domain_name": "产品经理基础",
    })
    _created_bank_ids.add(result["bank_id"])
    with SessionLocal() as session:
        bank = session.get(QuestionBankModel, result["bank_id"])
        assert bank is not None and bank.domain_id.startswith("custom_")
        manifest = get_domain(bank.domain_id)
        assert manifest.display_name == "产品经理基础"
        assert manifest.tutor_policy == "general_learning"
        assert manifest.doctor_review_required is False


def test_deleting_published_bank_releases_review_batch_for_republish() -> None:
    content = json.dumps(
        {"question": "删除题库后审核结果仍可继续吗？", "question_type": "判断", "answer": "正确"},
        ensure_ascii=False,
    )
    with TestClient(app) as client:
        created = client.post("/api/v3/factory/import-batches", json={
            "format": "jsonl",
            "content": content,
            "domain_id": "general_science",
            "source_name": "删除关联回归样例",
        })
        assert created.status_code == 200
        batch = created.json()["item"]
        approved = client.post(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/review",
            json={"status": "approved"},
        )
        assert approved.status_code == 200
        published = client.post(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/publish",
            json={"mode": "create_bank", "bank_name": "删除关联回归题库"},
        )
        assert published.status_code == 200
        bank_id = published.json()["item"]["bank_id"]
        _created_bank_ids.add(bank_id)

        deleted = client.delete(f"/api/v3/question-banks/{bank_id}")
        assert deleted.status_code == 200
        reopened = client.get(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert reopened.status_code == 200
        item = reopened.json()["item"]
        assert item["published_bank_id"] is None
        assert item["published_count"] == 0
        assert item["approved_count"] == 1
        assert item["items"][0]["status"] == "approved"

        deleted_batch = client.delete(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert deleted_batch.status_code == 200
