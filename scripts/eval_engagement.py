from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Settings
from src.medical_agent import MedicalAgentService
from src.medical_memory import PatientMemoryStore
from src.medical_rag import HashEmbeddings, MedicalRAGService
from src.schemas import ChatRequest


@dataclass(frozen=True)
class EngagementCase:
    session_id: str
    message: str
    generic_baseline: str


BENCHMARK_CASES = [
    EngagementCase(
        session_id="eval-anxious",
        message="I am worried about chest pain and whether Medicare covers preventive screening.",
        generic_baseline=(
            "I understand the worry. Chest pain can be urgent, so a clinician should review it, "
            "and Medicare may cover some preventive screening."
        ),
    ),
    EngagementCase(
        session_id="eval-confused",
        message="I do not understand if Part B covers flu shots or only doctor visits.",
        generic_baseline=(
            "I understand this is confusing. Part B may cover some preventive services and doctor visits, "
            "and you can call Medicare for coverage details."
        ),
    ),
    EngagementCase(
        session_id="eval-distressed",
        message="The pain is severe and I cannot breathe normally.",
        generic_baseline=(
            "Breathing trouble can be urgent. If this is happening now, seek urgent care and tell the "
            "clinician when it started."
        ),
    ),
    EngagementCase(
        session_id="eval-sad",
        message="I feel hopeless because I keep missing follow up appointments.",
        generic_baseline=(
            "I am sorry this feels hard. You can schedule a reminder, ask your clinic to reschedule, "
            "and review the plan with a clinician."
        ),
    ),
]


EMPATHY_TERMS = {
    "hear",
    "understand",
    "worried",
    "feel",
    "focused",
    "practical",
    "support",
    "frustrating",
    "sorry",
}
SAFETY_TERMS = {
    "emergency",
    "911",
    "urgent",
    "licensed clinician",
    "clinician",
    "diagnosis",
    "not a diagnosis",
    "medical decisions",
}
NEXT_STEP_TERMS = {
    "share",
    "confirm",
    "review",
    "seek",
    "call",
    "schedule",
    "reminder",
    "duration",
    "severity",
    "location",
}
GROUNDING_TERMS = {
    "medicare",
    "knowledge base",
    "source",
    "coverage",
    "part b",
    "guideline",
}


def _contains_any(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _question_count(text: str) -> int:
    return text.count("?")


def score_response(response: str) -> dict[str, float | bool]:
    text = response.lower()
    words = re.findall(r"[a-z0-9]+", text)
    concise = len(words) <= 180
    asks_focused_question = 0 < _question_count(response) <= 2 or _contains_any(text, {"share", "confirm"})

    dimensions: dict[str, bool] = {
        "empathy": _contains_any(text, EMPATHY_TERMS),
        "safety_boundary": _contains_any(text, SAFETY_TERMS),
        "focused_follow_up": asks_focused_question,
        "actionable_next_step": _contains_any(text, NEXT_STEP_TERMS),
        "source_grounding": _contains_any(text, GROUNDING_TERMS),
        "concise_plain_language": concise,
    }
    weights = {
        "empathy": 2.0,
        "safety_boundary": 2.0,
        "focused_follow_up": 2.0,
        "actionable_next_step": 2.0,
        "source_grounding": 1.0,
        "concise_plain_language": 1.0,
    }
    score = sum(weights[name] for name, passed in dimensions.items() if passed)
    return {**dimensions, "score": round(score, 2)}


async def run_engagement_benchmark() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="medical-engagement-eval-") as temp_dir:
        temp_path = Path(temp_dir)
        settings = Settings(
            OPENAI_API_KEY=None,
            EMBEDDING_API_KEY=None,
            FAISS_INDEX_DIR=str(temp_path / "faiss"),
            CHROMA_PERSIST_DIR=str(temp_path / "chroma"),
            USE_OFFLINE_MEDICARE_SAMPLE=True,
        )
        rag_service = MedicalRAGService(settings=settings, embeddings=HashEmbeddings())
        memory_store = PatientMemoryStore(settings=settings)
        service = MedicalAgentService(
            settings=settings,
            rag_service=rag_service,
            memory_store=memory_store,
        )

        rows: list[dict[str, Any]] = []
        for case in BENCHMARK_CASES:
            agent_response = await service.chat(ChatRequest(session_id=case.session_id, message=case.message))
            baseline_score = score_response(case.generic_baseline)
            agent_score = score_response(agent_response.answer)
            rows.append(
                {
                    "session_id": case.session_id,
                    "message": case.message,
                    "emotion": agent_response.emotion.model_dump(),
                    "baseline_score": baseline_score,
                    "agent_score": agent_score,
                    "llm_provider": agent_response.llm_provider,
                    "citations": [citation.model_dump() for citation in agent_response.citations],
                    "safety_flags": [flag.model_dump() for flag in agent_response.safety_flags],
                }
            )

        baseline_avg = sum(float(row["baseline_score"]["score"]) for row in rows) / len(rows)
        agent_avg = sum(float(row["agent_score"]["score"]) for row in rows) / len(rows)
        relative_lift = ((agent_avg - baseline_avg) / baseline_avg * 100) if baseline_avg else 0.0

        return {
            "benchmark": "offline_patient_comfort_engagement",
            "note": "Heuristic offline benchmark; does not call OpenAI and is not a clinical outcomes study.",
            "baseline": "generic non-memory support response",
            "agent": "current MedicalAgentService local_fallback with emotion, safety, RAG citations, and memory update",
            "case_count": len(rows),
            "baseline_average_score": round(baseline_avg, 2),
            "agent_average_score": round(agent_avg, 2),
            "relative_lift_percent": round(relative_lift, 1),
            "score_max": 10,
            "rows": rows,
        }


def print_report(result: dict[str, Any]) -> None:
    print("Patient comfort and engagement benchmark")
    print(f"Mode: {result['note']}")
    print(f"Baseline: {result['baseline']}")
    print(f"Agent: {result['agent']}")
    print(
        "Average score: "
        f"baseline {result['baseline_average_score']:.2f}/{result['score_max']} vs "
        f"agent {result['agent_average_score']:.2f}/{result['score_max']}"
    )
    print(f"Relative lift: {result['relative_lift_percent']:.1f}%")
    print("\nCases:")
    for row in result["rows"]:
        print(
            f"- {row['session_id']} emotion={row['emotion']['emotion']} "
            f"baseline={row['baseline_score']['score']} agent={row['agent_score']['score']} "
            f"provider={row['llm_provider']}"
        )
    print("\nJSON:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    print_report(asyncio.run(run_engagement_benchmark()))
