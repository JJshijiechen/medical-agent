from dataclasses import dataclass
from typing import Iterable, List

from .schemas import SafetyFlag, TriageLevel


MEDICAL_DISCLAIMER = (
    "I can help organize symptoms and Medicare guidance, but I cannot diagnose or replace a licensed clinician."
)


@dataclass(frozen=True)
class RedFlagRule:
    code: str
    keywords: tuple[str, ...]
    message: str
    severity: str = "high"


RED_FLAG_RULES = [
    RedFlagRule(
        code="chest_pain",
        keywords=("chest pain", "pressure in my chest", "胸痛", "胸口痛"),
        message="Chest pain or pressure can be urgent, especially with shortness of breath, sweating, nausea, or arm/jaw pain.",
    ),
    RedFlagRule(
        code="breathing",
        keywords=("can't breathe", "cannot breathe", "difficulty breathing", "shortness of breath", "喘不上气", "呼吸困难"),
        message="Trouble breathing can be a medical emergency.",
    ),
    RedFlagRule(
        code="stroke",
        keywords=("face drooping", "slurred speech", "one-sided weakness", "stroke", "中风", "口齿不清", "半边无力"),
        message="Stroke-like symptoms need immediate emergency evaluation.",
        severity="crisis",
    ),
    RedFlagRule(
        code="severe_bleeding",
        keywords=("severe bleeding", "won't stop bleeding", "大量出血", "血止不住"),
        message="Severe or uncontrolled bleeding needs urgent care.",
    ),
    RedFlagRule(
        code="suicide_self_harm",
        keywords=("suicide", "kill myself", "self harm", "want to die", "自杀", "不想活"),
        message="Self-harm or suicidal thoughts require immediate support from emergency services or a crisis line.",
        severity="crisis",
    ),
    RedFlagRule(
        code="overdose",
        keywords=("overdose", "too many pills", "poison", "服药过量", "中毒"),
        message="Possible overdose or poisoning requires urgent medical help.",
        severity="crisis",
    ),
]


def detect_red_flags(text: str, rules: Iterable[RedFlagRule] = RED_FLAG_RULES) -> List[SafetyFlag]:
    lowered = text.lower()
    flags: List[SafetyFlag] = []
    for rule in rules:
        if any(keyword.lower() in lowered for keyword in rule.keywords):
            flags.append(
                SafetyFlag(
                    code=rule.code,
                    message=rule.message,
                    severity=rule.severity,  # type: ignore[arg-type]
                )
            )
    return flags


def triage_from_flags(flags: List[SafetyFlag]) -> TriageLevel:
    if any(flag.severity == "crisis" for flag in flags):
        return "emergency"
    if any(flag.severity == "high" for flag in flags):
        return "urgent"
    if any(flag.severity == "moderate" for flag in flags):
        return "soon"
    return "routine"


def emergency_instruction(flags: List[SafetyFlag]) -> str | None:
    if not flags:
        return None
    if any(flag.severity in {"high", "crisis"} for flag in flags):
        return "If these symptoms are happening now or worsening, call 911 or seek emergency care immediately."
    return None
