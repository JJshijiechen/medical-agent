# Medical Agent Project Guide

## Purpose

This project is a patient-centric medical AI agent prototype for virtual consultations. It demonstrates multi-turn, context-aware conversations, long-term patient memory, emotion detection, Medicare guideline retrieval, symptom intake, form validation, and follow-up reminder workflows.

The agent is a clinical support and intake assistant. It must not diagnose, prescribe, or replace a licensed clinician.

## Current Demo Status

- Frontend console: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`
- API health: `GET /health`
- Chat route: `POST /api/v1/chat`
- OpenAI route indicator: chat responses include `llm_provider`, such as `openai:gpt-4o` or `local_fallback`.
- Offline retrieval benchmark: baseline 80% top-1 accuracy vs RAG 100%, for a 25.0% relative lift.
- Offline comfort/engagement benchmark: baseline 6.50/10 vs agent 9.00/10, for a 38.5% relative lift.

If `llm_provider` starts with `openai`, the request used the configured OpenAI API key and consumed OpenAI tokens. If it is `local_fallback`, the response came from the local fallback template.

## Agent Capabilities

- Medical chat with safety boundaries and source-grounded Medicare answers.
- Emotion detection with `emotion`, `score`, `risk_level`, and `comfort_strategy`.
- Red flag detection for symptoms such as chest pain, trouble breathing, stroke-like symptoms, severe bleeding, overdose, and self-harm.
- Long-term patient memory for symptom summaries, emotion trend, and follow-up history.
- Medicare RAG using offline sample guidance plus optional official URL ingestion.
- FAISS, ChromaDB, and in-memory retrieval paths with citations.
- FastAPI endpoints with dependency injection for testability.
- Frontend console for demos.
- Slack and Telegram bot entrypoints that share the same medical agent service.
- Google Calendar reminder workflow with dry-run behavior when credentials are not valid.

## Core Architecture

- `src/Server.py`: FastAPI app, dependency injection, static frontend, API routes.
- `src/medical_agent.py`: Main medical chat orchestration, OpenAI call, fallback logic, citations, safety flags.
- `src/medical_rag.py`: Medicare RAG service, chunking, metadata filtering, FAISS/Chroma/memory retrieval.
- `src/medical_emotion.py`: Deterministic emotion detector for routing and tests.
- `src/medical_safety.py`: Medical red flag rules and emergency guidance.
- `src/medical_memory.py`: Redis-backed patient profile memory with in-process fallback.
- `src/symptoms.py`: Real-time symptom intake and triage extraction.
- `src/forms.py`: Medicare and symptom intake form validation.
- `src/workflows.py`: Google Calendar follow-up reminders and Slack/Telegram notification dispatch.
- `src/static/`: Browser frontend console.
- `tests/`: Unit and API tests.

## Public API

### `POST /api/v1/chat`

Runs the full medical agent conversation flow.

Returns:

- `answer`
- `llm_provider`
- `emotion`
- `citations`
- `safety_flags`
- `next_steps`
- `session_id`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"Does Medicare Part B cover preventive screening?"}'
```

### `POST /api/v1/symptom-intake`

Extracts symptom details, missing intake fields, red flags, and triage level. This route does not call OpenAI.

### `POST /api/v1/forms/validate`

Validates Medicare intake or symptom intake forms. This route does not call OpenAI.

### `POST /api/v1/reminders`

Creates a follow-up reminder through Google Calendar when credentials are valid. Otherwise returns `dry_run`.

### `POST /api/v1/knowledge/ingest`

Ingests offline Medicare sample docs and/or official Medicare URLs into the RAG service.

## Frontend Demo

Start the server:

```bash
.venv/bin/python -m src.Server
```

Open:

```text
http://127.0.0.1:8000/
```

The frontend includes:

- Chat panel for medical conversation.
- Intake panel for symptom extraction.
- Forms panel for Medicare intake validation.
- Workflow panel for follow-up reminders.
- Right-side inspector for model route, emotion, safety flags, citations, and raw JSON.

Use `Model route` in the right inspector to confirm whether a response used OpenAI or local fallback.

## OpenAI and Token Usage

The project uses OpenAI only when the required packages and `.env` values are present:

- `OPENAI_API_KEY`
- `BASE_MODEL`, for example `gpt-4o`
- `EMBEDDING_MODEL`, for example `text-embedding-3-small`

Calls that can consume OpenAI tokens:

- `POST /api/v1/chat`
- RAG embedding generation during knowledge ingestion or retrieval if OpenAI embeddings are active

Calls that do not consume OpenAI tokens:

- `GET /health`
- `POST /api/v1/symptom-intake`
- `POST /api/v1/forms/validate`
- `POST /api/v1/reminders` in dry-run mode
- Static frontend loading

To avoid token usage, remove or comment out `OPENAI_API_KEY` in `.env` and restart the server. The agent will use local fallback behavior.

## RAG Data Sources

Offline sample docs are defined in `src/medicare_corpus.py`.

Official seed URLs:

- CMS Preventive Services
- Medicare Preventive and Screening Services
- Medicare Part B Coverage
- CMS National Coverage Determinations Manual

Metadata fields include:

- `source_type`
- `topic`
- `coverage_area`
- `year`
- `url`
- `title`

## Evaluation Evidence

Use these commands to verify the resume-style percentage claims without spending OpenAI tokens:

```bash
.venv/bin/python scripts/eval_retrieval.py
.venv/bin/python scripts/eval_engagement.py
```

Retrieval benchmark:

- Compares a weighted lexical baseline against the current Medicare RAG service.
- Uses the offline Medicare sample corpus, HashEmbeddings, FAISS, ChromaDB, and in-memory retrieval.
- Current result: top-1 retrieval accuracy improves from 80% to 100%, a 25.0% relative lift.

Comfort and engagement benchmark:

- Compares generic support responses against `MedicalAgentService` local fallback responses.
- Scores empathy, safety boundary, focused follow-up, actionable next step, source grounding, and concise language.
- Current result: score improves from 6.50/10 to 9.00/10, a 38.5% relative lift.
- This is an offline heuristic estimate, not a clinical study or patient trial.

## Safety Rules

The agent should:

- Never claim to diagnose or prescribe.
- Recommend licensed clinician review for medical decisions.
- Use retrieved Medicare context for coverage claims.
- Say the knowledge base does not cover the answer when citations are unavailable.
- Prioritize emergency care guidance when red flags are detected.

## Running Tests

```bash
.venv/bin/python -m pytest -q
```

Expected current status:

```text
15 passed
```

Warnings from FAISS/OpenTelemetry may appear and are not test failures.

## Useful Commands

Start API and frontend:

```bash
.venv/bin/python -m src.Server
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

No-token symptom intake smoke test:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/symptom-intake \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","text":"I have chest pain for 2 days, severity 8/10"}'
```

OpenAI chat test:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"Does Medicare Part B cover preventive screening?"}'
```

Knowledge ingest:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"use_offline_sample":true}'
```

## Known Limits

- Google Calendar may return `dry_run` until OAuth credentials are refreshed.
- Slack and Telegram require valid bot tokens.
- Official Medicare URL ingestion requires network access.
- The local fallback is useful for demos and tests, but production-quality medical answers should use the configured OpenAI route with citations.
