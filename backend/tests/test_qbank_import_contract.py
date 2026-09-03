from pathlib import Path

from app.services.question_bank_import_service import question_bank_import_service


def test_explanation_is_optional_and_defaults_to_none_marker() -> None:
    payload = {
        "format": "jsonl",
        "source_name": "import-contract-test",
        "content": '{"question":"RAG 是什么？","question_type":"单选","options":["检索增强生成","随机生成"],"answer":"检索增强生成"}\n',
    }

    result = question_bank_import_service.validate(payload)

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 0
    assert result["ready_to_publish"] is True
    assert result["items"][0]["explanation"] == "无"

    blank_payload = {
        **payload,
        "content": '{"question":"空解析题？","question_type":"单选","options":["是","否"],"answer":"否","explanation":""}\n',
    }
    blank_result = question_bank_import_service.validate(blank_payload)
    assert blank_result["accepted_count"] == 1
    assert blank_result["rejected_count"] == 0
    assert blank_result["items"][0]["explanation"] == "无"


def test_sample_metadata_declares_explanation_optional() -> None:
    metadata_path = Path(__file__).resolve().parents[2] / "临时生成题库目录" / "题库元数据.json"
    metadata = metadata_path.read_text(encoding="utf-8")
    assert '"explanation"' not in metadata.split('"required_fields"', 1)[1].split('"question_type_values"', 1)[0]
    assert '"explanation"' in metadata.split('"optional_fields"', 1)[1]
