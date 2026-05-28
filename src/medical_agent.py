from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from .config import Settings, get_settings
from .medical_emotion import EmotionDetector
from .medical_memory import PatientMemoryStore
from .medical_rag import MedicalRAGService, RagHit
from .medical_safety import MEDICAL_DISCLAIMER, detect_red_flags, emergency_instruction
from .schemas import ChatRequest, ChatResponse, EmotionResult, SafetyFlag


class MedicalAgentService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        rag_service: Optional[MedicalRAGService] = None,
        memory_store: Optional[PatientMemoryStore] = None,
        emotion_detector: Optional[EmotionDetector] = None,
    ):
        self.settings = settings or get_settings()
        self.rag_service = rag_service or MedicalRAGService(self.settings)
        self.memory_store = memory_store or PatientMemoryStore(self.settings)
        self.emotion_detector = emotion_detector or EmotionDetector()
        self.llm = self._build_llm()

    def _build_llm(self):
        if not self.settings.openai_api_key:
            return None
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=self.settings.base_model,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_api_base,
                temperature=0.2,
            )
        except Exception:
            return None

    async def chat(self, request: ChatRequest) -> ChatResponse:
        emotion = self.emotion_detector.detect(request.message)
        safety_flags = detect_red_flags(request.message)
        hits = self.rag_service.retrieve(request.message, metadata_filter=request.metadata_filter)
        citations = self.rag_service.citations_from_hits(hits)
        profile = self.memory_store.get_profile(request.session_id)
        answer, llm_provider = await self._generate_answer(request, emotion, safety_flags, hits, profile)
        next_steps = self._next_steps(safety_flags, hits)
        self.memory_store.update_after_chat(request.session_id, request.message, emotion, safety_flags)
        return ChatResponse(
            answer=answer,
            llm_provider=llm_provider,
            emotion=emotion,
            citations=citations,
            safety_flags=safety_flags,
            next_steps=next_steps,
            session_id=request.session_id,
        )

    async def _generate_answer(
        self,
        request: ChatRequest,
        emotion: EmotionResult,
        safety_flags: list[SafetyFlag],
        hits: list[RagHit],
        profile: dict,
    ) -> tuple[str, str]:
        context = "\n\n".join(
            f"Source: {hit.document.metadata.get('title')}\nURL: {hit.document.metadata.get('url')}\n{hit.document.page_content}"
            for hit in hits
        )
        safety_note = emergency_instruction(safety_flags)
        if self.llm is None:
            return self._fallback_answer(request.message, emotion, safety_flags, hits, safety_note), "local_fallback"

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are a patient-centric medical assistant for virtual consultations.
You help with symptom intake, Medicare guideline retrieval, form validation context, and follow-up planning.
You must not diagnose, prescribe, or claim clinical certainty.
Use a calm, empathetic tone and adapt to the detected emotion strategy.
For Medicare coverage questions, use only the retrieved context. If context is missing, say the knowledge base does not cover it.
Include source titles inline when you use retrieved Medicare guidance.
Always recommend licensed clinician review for medical decisions.
If red flags are present, prioritize emergency guidance before other content.
""",
                ),
                (
                    "human",
                    """
Patient message: {message}

Patient profile memory:
{profile}

Detected emotion:
{emotion}

Safety flags:
{safety_flags}

Retrieved Medicare context:
{context}

Medical safety note:
{safety_note}

Write a concise, supportive answer with actionable next steps.
""",
                ),
            ]
        )
        chain = prompt | self.llm
        try:
            response = await chain.ainvoke(
                {
                    "message": request.message,
                    "profile": profile,
                    "emotion": emotion.model_dump(),
                    "safety_flags": [flag.model_dump() for flag in safety_flags],
                    "context": context or "No matching Medicare knowledge base context was retrieved.",
                    "safety_note": safety_note or MEDICAL_DISCLAIMER,
                }
            )
            return response.content, f"openai:{self.settings.base_model}"
        except Exception:
            return self._fallback_answer(request.message, emotion, safety_flags, hits, safety_note), "local_fallback"

    def _fallback_answer(
        self,
        message: str,
        emotion: EmotionResult,
        safety_flags: list[SafetyFlag],
        hits: list[RagHit],
        safety_note: str | None,
    ) -> str:
        parts = [MEDICAL_DISCLAIMER]
        if safety_note:
            parts.insert(0, safety_note)
        parts.append(f"I hear that this may feel {emotion.emotion}; I will keep this focused and practical.")
        if hits:
            best = hits[0]
            title = best.document.metadata.get("title", "Medicare guideline")
            parts.append(f"Relevant Medicare knowledge base match: {title}. {best.document.page_content[:420]}")
        else:
            parts.append("The Medicare knowledge base did not cover this specific question, so I should not make a coverage claim.")
        if not safety_flags:
            parts.append("To continue intake, share the symptom duration, severity from 1-10, location, medications tried, and allergies.")
        return "\n\n".join(parts)

    @staticmethod
    def _next_steps(safety_flags: list[SafetyFlag], hits: list[RagHit]) -> list[str]:
        steps: list[str] = []
        if emergency_instruction(safety_flags):
            steps.append("Seek emergency care now if the red-flag symptom is current or worsening.")
        steps.append("Confirm symptom duration, severity, location, medications tried, and allergies.")
        steps.append("Review medical decisions with a licensed clinician.")
        if not hits:
            steps.append("Ingest the relevant Medicare guideline or official coverage page before making a coverage determination.")
        return steps
