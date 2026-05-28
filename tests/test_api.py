from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.Server import app, get_medical_agent_service, get_rag_service, get_reminder_workflow
from src.schemas import ChatResponse, EmotionResult, KnowledgeIngestResponse, ReminderResponse


class FakeAgent:
    async def chat(self, request):
        return ChatResponse(
            answer="Test answer with medical safety boundaries.",
            emotion=EmotionResult(emotion="calm", score=2, risk_level="low", comfort_strategy="Clear and concise."),
            citations=[],
            safety_flags=[],
            next_steps=["Confirm symptom duration."],
            session_id=request.session_id,
        )


class FakeRag:
    def ingest_offline_sample(self):
        return KnowledgeIngestResponse(status="success", document_count=1, chunk_count=2, backends=["memory"], message="ok")

    def ingest_urls(self, urls=None, metadata=None):
        return KnowledgeIngestResponse(status="success", document_count=1, chunk_count=2, backends=["memory"], message="ok")


class FakeWorkflow:
    async def create_reminder(self, request):
        start = request.start_time or datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        return ReminderResponse(
            status="dry_run",
            summary="Patient follow-up: test",
            start_time=start,
            end_time=start,
            calendar_event={"status": "dry_run"},
            notifications=[{"channel": request.channel, "status": "dry_run"}],
            message="Follow-up reminder set.",
        )


def test_chat_endpoint_with_dependency_override():
    app.dependency_overrides[get_medical_agent_service] = lambda: FakeAgent()
    client = TestClient(app)
    response = client.post("/api/v1/chat", json={"session_id": "s1", "message": "hello"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["session_id"] == "s1"


def test_frontend_route_serves_console():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Medical Agent Console" in response.text


def test_symptom_intake_endpoint():
    client = TestClient(app)
    response = client.post("/api/v1/symptom-intake", json={"session_id": "s1", "text": "fever for 2 days severity 5/10"})

    assert response.status_code == 200
    assert response.json()["captured"]["severity"] == 5


def test_form_validation_endpoint():
    client = TestClient(app)
    response = client.post(
        "/api/v1/forms/validate",
        json={"form_type": "symptom_intake", "fields": {"primary_symptom": "pain", "duration": "today", "severity": 4}},
    )

    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_knowledge_ingest_endpoint_with_dependency_override():
    app.dependency_overrides[get_rag_service] = lambda: FakeRag()
    client = TestClient(app)
    response = client.post("/api/v1/knowledge/ingest", json={"use_offline_sample": True})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["chunk_count"] == 2


def test_reminder_endpoint_with_dependency_override():
    app.dependency_overrides[get_reminder_workflow] = lambda: FakeWorkflow()
    client = TestClient(app)
    response = client.post("/api/v1/reminders", json={"session_id": "s1", "user_text": "remind me tomorrow", "channel": "api"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "dry_run"
