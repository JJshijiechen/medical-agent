# Patient-Centric Medical Agent

Production-style prototype for a medical AI agent. It supports multi-turn patient conversations, long-term memory, emotion detection, Medicare RAG over official guidance, symptom intake, medical form validation, and follow-up reminders through Google Calendar with Slack and Telegram delivery.

This project is a clinical support and intake assistant. It does not diagnose, prescribe, or replace licensed medical care.

## Core Features

- LangChain/OpenAI chat service with a medical-safety persona and deterministic offline fallback.
- Redis-backed patient profile memory for symptom summaries, follow-up reminders, and emotion trend.
- Emotion detection returning `emotion`, `score`, `risk_level`, and `comfort_strategy`.
- FastAPI v1 endpoints for chat, symptom intake, form validation, reminder creation, and knowledge ingestion.
- Medicare RAG with document chunking, metadata filtering, cosine-style retrieval, source citations, FAISS, ChromaDB, and an in-memory fallback for local tests.
- Offline Medicare sample corpus plus optional official URL ingestion.
- Slack Socket Mode bot and Telegram bot sharing the same `MedicalAgentService`.
- Google Calendar follow-up reminders with dry-run behavior when credentials are not configured.

## API

Start the API:

```bash
poetry install
poetry run uvicorn src.Server:app --host 0.0.0.0 --port 8000
```

Open docs at `http://localhost:8000/docs`.

Open the frontend console at `http://localhost:8000/`.

Endpoints:

- `POST /api/v1/chat`
- `POST /api/v1/symptom-intake`
- `POST /api/v1/forms/validate`
- `POST /api/v1/reminders`
- `POST /api/v1/knowledge/ingest`
- `POST /add_urls` for backward compatibility

Example:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"I am worried about chest pain and whether Medicare covers preventive screening."}'
```

## Configuration

Create `.env` in the project root:

```env
OPENAI_API_KEY=your_openai_key
BASE_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
REDIS_URL=redis://localhost:6379/0

FAISS_INDEX_DIR=./vector_db/faiss
CHROMA_PERSIST_DIR=./vector_db/chroma
CHROMA_COLLECTION=medicare_guidelines
USE_OFFLINE_MEDICARE_SAMPLE=true
MEDICARE_GUIDELINE_URLS=https://www.cms.gov/medicare/coverage/preventive-services-coverage,https://www.medicare.gov/coverage/preventive-screening-services?linkId=134567254,https://www.medicare.gov/what-medicare-covers/what-part-b-covers,https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/ncd103c1_part1.pdf

GOOGLE_CALENDAR_ID=primary
DEFAULT_TIMEZONE=America/Chicago
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token
TELEGRAM_BOT_TOKEN=your-telegram-token
```

If OpenAI or Google credentials are missing, the app still runs with local deterministic embeddings and dry-run reminders.

## Medicare Knowledge

Initialize the offline sample corpus:

```bash
poetry run python -m src.init_vector_store
```

Ingest official Medicare/CMS sources through the API:

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"use_official_urls":true,"use_offline_sample":true}'
```

Official seed sources:

- CMS Preventive Services: https://www.cms.gov/medicare/coverage/preventive-services-coverage
- Medicare Preventive & Screening Services: https://www.medicare.gov/coverage/preventive-screening-services?linkId=134567254
- Medicare Part B Coverage: https://www.medicare.gov/what-medicare-covers/what-part-b-covers
- CMS National Coverage Determinations Manual: https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/ncd103c1_part1.pdf

## Evaluation Benchmarks

These benchmarks are offline demo evidence for the resume metrics. They do not call OpenAI and should not be described as clinical outcome studies.

Run Medicare retrieval evaluation:

```bash
poetry run python scripts/eval_retrieval.py
```

Current result:

```text
Top-1 accuracy: baseline 80% vs RAG 100%
Relative top-1 lift: 25.0%
```

Run patient comfort and engagement evaluation:

```bash
poetry run python scripts/eval_engagement.py
```

Current result:

```text
Average score: baseline 6.50/10 vs agent 9.00/10
Relative lift: 38.5%
```

The comfort and engagement score is a deterministic heuristic over empathy, safety boundaries, focused follow-up, actionable next steps, source grounding, and concise language.

## Slack, Telegram, and Docker

Run Redis and API:

```bash
docker compose up api redis
```

Run Slack worker:

```bash
docker compose --profile slack up slack_bot
```

Run Telegram worker:

```bash
docker compose --profile telegram up telegram_bot
```

Local worker commands:

```bash
poetry run python -m src.SlackWebHook
poetry run python -m src.TelegramBot
```

## Tests

```bash
poetry run pytest
```

The test suite uses offline embeddings, FastAPI dependency overrides, and dry-run workflow services so it does not require OpenAI, Google, Slack, or Telegram credentials.
