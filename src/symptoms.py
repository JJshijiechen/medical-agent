import re
from typing import Any, Dict, List

from .medical_safety import detect_red_flags, triage_from_flags
from .schemas import SymptomIntakeRequest, SymptomIntakeResponse


REQUIRED_FIELDS = [
    "primary_symptom",
    "duration",
    "severity",
    "location",
    "medications",
    "allergies",
]


QUESTION_BY_FIELD = {
    "primary_symptom": "What symptom is bothering you the most right now?",
    "duration": "When did this start, and has it changed over time?",
    "severity": "On a 1-10 scale, how severe is it right now?",
    "location": "Where in your body do you feel it?",
    "medications": "What medications, supplements, or treatments have you already taken?",
    "allergies": "Do you have any medication or food allergies?",
}


class SymptomIntakeService:
    SYMPTOM_WORDS = (
        "pain",
        "fever",
        "cough",
        "rash",
        "nausea",
        "dizzy",
        "headache",
        "fatigue",
        "shortness of breath",
        "疼",
        "发烧",
        "咳嗽",
        "头痛",
        "恶心",
        "头晕",
    )

    def intake(self, request: SymptomIntakeRequest) -> SymptomIntakeResponse:
        captured = dict(request.structured)
        text = request.text.strip()
        captured.setdefault("original_text", text)

        if "primary_symptom" not in captured:
            captured["primary_symptom"] = self._extract_symptom(text)
        if "severity" not in captured:
            severity = self._extract_severity(text)
            if severity is not None:
                captured["severity"] = severity
        if "duration" not in captured:
            duration = self._extract_duration(text)
            if duration:
                captured["duration"] = duration
        if "location" not in captured:
            location = self._extract_location(text)
            if location:
                captured["location"] = location

        missing = [field for field in REQUIRED_FIELDS if not captured.get(field)]
        flags = detect_red_flags(text)
        triage = triage_from_flags(flags)
        if triage == "routine" and captured.get("severity", 0):
            try:
                severity_value = int(captured["severity"])
                if severity_value >= 8:
                    triage = "urgent"
                elif severity_value >= 6:
                    triage = "soon"
            except (TypeError, ValueError):
                pass

        return SymptomIntakeResponse(
            captured=captured,
            missing_fields=missing,
            red_flags=flags,
            triage_level=triage,
            next_questions=[QUESTION_BY_FIELD[field] for field in missing[:3]],
        )

    def _extract_symptom(self, text: str) -> str | None:
        lowered = text.lower()
        for symptom in self.SYMPTOM_WORDS:
            if symptom in lowered:
                return symptom
        return None

    def _extract_severity(self, text: str) -> int | None:
        patterns = [
            r"(\d{1,2})\s*/\s*10",
            r"severity\s*(?:is|:)?\s*(\d{1,2})",
            r"pain\s*(?:is|:)?\s*(\d{1,2})",
            r"疼痛?等级\s*(\d{1,2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = int(match.group(1))
                if 1 <= value <= 10:
                    return value
        return None

    def _extract_duration(self, text: str) -> str | None:
        match = re.search(
            r"((?:for|since)\s+[^,.!?]+|\d+\s*(?:hour|hours|day|days|week|weeks|month|months)|\d+\s*(?:小时|天|周|个月))",
            text,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    def _extract_location(self, text: str) -> str | None:
        match = re.search(r"\b(?:in|on|around)\s+(my\s+)?([a-z ]{3,30})", text, flags=re.IGNORECASE)
        if match:
            return match.group(2).strip()
        for body_part in ("chest", "head", "abdomen", "stomach", "back", "leg", "arm", "胸", "头", "腹", "背"):
            if body_part in text.lower():
                return body_part
        return None
