from app.core.config import SAFETY_NOTICE


class SafetyService:
    risky_terms = ["确诊", "立即手术", "必须活检", "直接开药", "保证治愈", "身份证", "住院号", "姓名："]
    sensitive_terms = ["身份证", "住院号", "就诊卡号", "姓名：", "手机号", "电话"]

    def review_text(self, text: str) -> dict[str, object]:
        warnings = [term for term in self.risky_terms if term in text]
        return {
            "passed": len(warnings) == 0,
            "warnings": [f"检测到可能越界或敏感表述：{term}" for term in warnings],
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
        }

    def add_notice(self, payload: dict[str, object]) -> dict[str, object]:
        payload["doctor_review_required"] = True
        payload["safety_notice"] = SAFETY_NOTICE
        return payload

    def redact_sensitive_text(self, text: str) -> str:
        redacted = text
        for term in self.sensitive_terms:
            redacted = redacted.replace(term, f"{term[0]}***")
        return redacted


safety_service = SafetyService()
