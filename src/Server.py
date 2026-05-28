import logging
from functools import lru_cache
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from .config import Settings, get_settings
from .forms import MedicalFormValidator
from .medical_agent import MedicalAgentService
from .medical_memory import PatientMemoryStore
from .medical_rag import MedicalRAGService
from .schemas import (
    ChatRequest,
    ChatResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    MedicalFormValidationRequest,
    MedicalFormValidationResponse,
    ReminderRequest,
    ReminderResponse,
    SymptomIntakeRequest,
    SymptomIntakeResponse,
)
from .symptoms import SymptomIntakeService
from .workflows import ReminderWorkflow


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("medical-agent-api")

app = FastAPI(
    title="Patient-Centric Medical Agent API",
    description="Medical AI agent with symptom intake, Medicare RAG, long-term memory, and follow-up workflows.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@lru_cache
def get_rag_service() -> MedicalRAGService:
    return MedicalRAGService(get_settings())


@lru_cache
def get_memory_store() -> PatientMemoryStore:
    return PatientMemoryStore(get_settings())


@lru_cache
def get_medical_agent_service() -> MedicalAgentService:
    settings = get_settings()
    return MedicalAgentService(
        settings=settings,
        rag_service=get_rag_service(),
        memory_store=get_memory_store(),
    )


@lru_cache
def get_symptom_intake_service() -> SymptomIntakeService:
    return SymptomIntakeService()


@lru_cache
def get_form_validator() -> MedicalFormValidator:
    return MedicalFormValidator()


@lru_cache
def get_reminder_workflow() -> ReminderWorkflow:
    settings = get_settings()
    return ReminderWorkflow(settings=settings, memory_store=get_memory_store())


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": settings.app_name,
        "offline_medicare_sample": settings.use_offline_medicare_sample,
    }


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: MedicalAgentService = Depends(get_medical_agent_service),
) -> ChatResponse:
    return await service.chat(request)


@app.post("/api/v1/symptom-intake", response_model=SymptomIntakeResponse)
async def symptom_intake(
    request: SymptomIntakeRequest,
    service: SymptomIntakeService = Depends(get_symptom_intake_service),
) -> SymptomIntakeResponse:
    return service.intake(request)


@app.post("/api/v1/forms/validate", response_model=MedicalFormValidationResponse)
async def validate_form(
    request: MedicalFormValidationRequest,
    validator: MedicalFormValidator = Depends(get_form_validator),
) -> MedicalFormValidationResponse:
    return validator.validate(request)


@app.post("/api/v1/reminders", response_model=ReminderResponse)
async def create_reminder(
    request: ReminderRequest,
    workflow: ReminderWorkflow = Depends(get_reminder_workflow),
) -> ReminderResponse:
    return await workflow.create_reminder(request)


@app.post("/api/v1/knowledge/ingest", response_model=KnowledgeIngestResponse)
async def ingest_knowledge(
    request: KnowledgeIngestRequest,
    rag_service: MedicalRAGService = Depends(get_rag_service),
    settings: Settings = Depends(get_settings),
) -> KnowledgeIngestResponse:
    responses: list[KnowledgeIngestResponse] = []
    if request.use_offline_sample:
        responses.append(rag_service.ingest_offline_sample())
    if request.use_official_urls or request.urls:
        urls = request.urls or settings.medicare_guideline_urls
        responses.append(rag_service.ingest_urls(urls=urls, metadata=request.metadata))
    if not responses:
        raise HTTPException(status_code=400, detail="Select offline sample, official URLs, or provide URLs.")

    document_count = sum(item.document_count for item in responses)
    chunk_count = sum(item.chunk_count for item in responses)
    backends = sorted({backend for item in responses for backend in item.backends})
    errors = [error for item in responses for error in item.errors]
    status = "error" if responses and all(item.status == "error" for item in responses) else "partial" if errors else "success"
    return KnowledgeIngestResponse(
        status=status,
        document_count=document_count,
        chunk_count=chunk_count,
        backends=backends,
        errors=errors,
        message=f"Ingested {chunk_count} chunks across {len(responses)} knowledge source groups.",
    )


class UrlRequest(BaseModel):
    urls: List[str]


@app.post("/add_urls", response_model=KnowledgeIngestResponse)
async def add_urls_legacy(
    request: UrlRequest,
    rag_service: MedicalRAGService = Depends(get_rag_service),
) -> KnowledgeIngestResponse:
    """Backward-compatible endpoint for the original classroom project."""
    if not request.urls:
        raise HTTPException(status_code=400, detail="URL list cannot be empty.")
    return rag_service.ingest_urls(urls=request.urls)


def main():
    import uvicorn

    uvicorn.run("src.Server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
