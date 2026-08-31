"""Small, explicit domain-pack registry for the shared learning platform.

This is deliberately configuration, not an executable plugin framework.  Core
services store and pass ``domain_id`` while each manifest supplies user-facing
metadata and the policy/namespace references owned by that domain pack.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from app.core.config import SAFETY_NOTICE


GENERAL_LEARNING_NOTICE = "用于通用学习训练与复盘；请以课程资料或教师指导为准。"
PLATFORM_NOTICE = "请按所选学习领域的资料、课程要求与使用边界完成练习和复盘。"


@dataclass(frozen=True)
class DomainManifest:
    domain_id: str
    display_name: str
    description: str
    subjects: tuple[str, ...]
    supported_question_types: tuple[str, ...]
    knowledge_namespaces: tuple[str, ...]
    tutor_policy: Literal["medical_education", "general_learning"]
    evaluation_pack_refs: tuple[str, ...]
    license_summary: str
    learner_notice: str
    doctor_review_required: bool

    def public_payload(self) -> dict[str, object]:
        """Return only catalog data; namespaces/policies remain internal."""

        return {
            "domain_id": self.domain_id,
            "display_name": self.display_name,
            "description": self.description,
            "subjects": list(self.subjects),
            "supported_question_types": list(self.supported_question_types),
        }


_ALL_QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false", "short_answer")

DOMAIN_MANIFESTS: dict[str, DomainManifest] = {
    "endoscopy": DomainManifest(
        domain_id="endoscopy",
        display_name="医疗 / 消化内镜",
        description="面向消化内镜教学训练的受治理题库、资料与 Tutor 策略。",
        subjects=("内镜图像观察", "消化系统", "临床医学"),
        supported_question_types=_ALL_QUESTION_TYPES,
        knowledge_namespaces=("medical_general", "gastroenterology", "endoscopy", "qbank_explanations", "user_uploaded", "factory_sources"),
        tutor_policy="medical_education",
        evaluation_pack_refs=("cmexam-text-eval-v1", "endobench-vlm-eval-v1"),
        license_summary="医疗资料与数据集受各自来源、授权和医生复核边界约束。",
        learner_notice=SAFETY_NOTICE,
        doctor_review_required=True,
    ),
    "general_science": DomainManifest(
        domain_id="general_science",
        display_name="通用科学",
        description="面向基础科学概念、证据推理与多选练习的独立学习域。",
        subjects=("物理", "化学", "生命科学", "地球与空间科学"),
        supported_question_types=("single_choice", "multiple_choice", "true_false"),
        knowledge_namespaces=("general_science",),
        tutor_policy="general_learning",
        evaluation_pack_refs=("general-science-text-eval-v1",),
        license_summary="ARC Easy 仅作为本地可验证导入源；上游 CC BY-SA 4.0 归属与署名要求保留。",
        learner_notice=GENERAL_LEARNING_NOTICE,
        doctor_review_required=False,
    ),
}


def get_domain(domain_id: str) -> DomainManifest:
    try:
        return DOMAIN_MANIFESTS[domain_id]
    except KeyError as exc:
        raise ValueError(f"unsupported domain_id: {domain_id}") from exc


def domain_ids() -> set[str]:
    return set(DOMAIN_MANIFESTS)


def list_public_domains() -> list[dict[str, object]]:
    return [manifest.public_payload() for manifest in DOMAIN_MANIFESTS.values()]


def tutor_policy_for(domain_id: str) -> DomainManifest:
    return get_domain(domain_id)
