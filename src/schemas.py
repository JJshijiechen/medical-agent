from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


EmotionName = Literal["calm", "anxious", "angry", "sad", "confused", "distressed", "positive"]
RiskLevel = Literal["low", "moderate", "high", "crisis"]
TriageLevel = Literal["self_care", "routine", "soon", "urgent", "emergency"]


class EmotionResult(BaseModel):
    emotion: EmotionName = "calm"
    score: int = Field(default=3, ge=1, le=10)
    risk_level: RiskLevel = "low"
    comfort_strategy: str = "Use clear, calm language and ask one focused follow-up question."


class SafetyFlag(BaseModel):
    code: str
    message: str
    severity: RiskLevel = "low"


class Citation(BaseModel):
    title: str
    url: Optional[str] = None
    source_type: str = "medicare_guideline"
    topic: Optional[str] = None
    coverage_area: Optional[str] = None
    year: Optional[int] = None
    score: Optional[float] = None
    backend: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(default="default")
    patient_id: Optional[str] = None
    metadata_filter: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    answer: str
    llm_provider: str = "local_fallback"
    emotion: EmotionResult
    citations: List[Citation] = Field(default_factory=list)
    safety_flags: List[SafetyFlag] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    session_id: str


class SymptomIntakeRequest(BaseModel):
    text: str = Field(min_length=1)
    session_id: str = Field(default="default")
    structured: Dict[str, Any] = Field(default_factory=dict)


class SymptomIntakeResponse(BaseModel):
    captured: Dict[str, Any]
    missing_fields: List[str]
    red_flags: List[SafetyFlag] = Field(default_factory=list)
    triage_level: TriageLevel = "routine"
    next_questions: List[str] = Field(default_factory=list)


class MedicalFormValidationRequest(BaseModel):
    form_type: str = Field(default="medicare_intake")
    fields: Dict[str, Any] = Field(default_factory=dict)


class FieldError(BaseModel):
    field: str
    message: str


class MedicalFormValidationResponse(BaseModel):
    is_valid: bool
    errors: List[FieldError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    normalized: Dict[str, Any] = Field(default_factory=dict)


class ReminderRequest(BaseModel):
    user_text: str = Field(min_length=1)
    session_id: str = Field(default="default")
    patient_id: Optional[str] = None
    channel: Literal["api", "slack", "telegram"] = "api"
    recipient: Optional[str] = None
    start_time: Optional[datetime] = None
    duration_minutes: int = Field(default=30, ge=5, le=240)


class ReminderResponse(BaseModel):
    status: Literal["created", "dry_run", "error"]
    summary: str
    start_time: datetime
    end_time: datetime
    calendar_event: Dict[str, Any] = Field(default_factory=dict)
    notifications: List[Dict[str, Any]] = Field(default_factory=list)
    message: str


class KnowledgeIngestRequest(BaseModel):
    urls: Optional[List[str]] = None
    use_official_urls: bool = False
    use_offline_sample: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("urls")
    @classmethod
    def clean_urls(cls, value):
        if value is None:
            return value
        return [url.strip() for url in value if url.strip()]


class KnowledgeIngestResponse(BaseModel):
    status: Literal["success", "partial", "error"]
    document_count: int = 0
    chunk_count: int = 0
    backends: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    message: str
