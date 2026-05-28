from __future__ import annotations

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

from langchain_core.documents import Document

from src.config import Settings
from src.medicare_corpus import OFFLINE_MEDICARE_DOCS
from src.medical_rag import HashEmbeddings, MedicalRAGService


@dataclass(frozen=True)
class RetrievalCase:
    query: str
    expected_topic: str


BENCHMARK_CASES = [
    RetrievalCase(
        query="Which Medicare Part B preventive screening services help detect problems early?",
        expected_topic="preventive_services",
    ),
    RetrievalCase(
        query="diagnose or treat a medical condition and preventive services such as flu shots",
        expected_topic="part_b",
    ),
    RetrievalCase(
        query="Are dental care hearing aids routine eye exams and cosmetic surgery covered?",
        expected_topic="not_covered",
    ),
    RetrievalCase(
        query="What determines Original Medicare coverage decisions and local coverage?",
        expected_topic="coverage_determination",
    ),
    RetrievalCase(
        query="What is the Welcome to Medicare preventive visit during the first 12 months?",
        expected_topic="wellness_visit",
    ),
]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _weighted_lexical_baseline(query: str, documents: list[Document]) -> str:
    query_tokens = _tokens(query)
    scored: list[tuple[float, int, Document]] = []
    for index, document in enumerate(documents):
        title_tokens = _tokens(str(document.metadata.get("title", "")))
        content_tokens = _tokens(document.page_content)
        score = len(query_tokens & title_tokens) * 2.0 + len(query_tokens & content_tokens) * 0.25
        scored.append((score, -index, document))
    best = max(scored, key=lambda item: (item[0], item[1]))[2]
    return str(best.metadata.get("topic"))


def _accuracy(results: list[dict[str, Any]], prediction_key: str) -> float:
    return sum(1 for row in results if row[prediction_key] == row["expected_topic"]) / len(results)


def run_retrieval_benchmark() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="medical-rag-eval-") as temp_dir:
        temp_path = Path(temp_dir)
        settings = Settings(
            OPENAI_API_KEY=None,
            EMBEDDING_API_KEY=None,
            FAISS_INDEX_DIR=str(temp_path / "faiss"),
            CHROMA_PERSIST_DIR=str(temp_path / "chroma"),
            USE_OFFLINE_MEDICARE_SAMPLE=True,
        )
        service = MedicalRAGService(settings=settings, embeddings=HashEmbeddings())
        ingest = service.ingest_offline_sample()

        rows: list[dict[str, Any]] = []
        for case in BENCHMARK_CASES:
            baseline_topic = _weighted_lexical_baseline(case.query, OFFLINE_MEDICARE_DOCS)
            hits = service.retrieve(case.query, k=3)
            rag_topics = [str(hit.document.metadata.get("topic")) for hit in hits]
            rows.append(
                {
                    "query": case.query,
                    "expected_topic": case.expected_topic,
                    "baseline_topic": baseline_topic,
                    "rag_top1_topic": rag_topics[0] if rag_topics else None,
                    "rag_top3_topics": rag_topics,
                    "top_citation": hits[0].document.metadata.get("title") if hits else None,
                    "backend": hits[0].backend if hits else None,
                    "score": round(hits[0].score, 4) if hits else None,
                }
            )

        baseline_top1 = _accuracy(rows, "baseline_topic")
        rag_top1 = _accuracy(rows, "rag_top1_topic")
        rag_top3 = sum(
            1 for row in rows if row["expected_topic"] in row["rag_top3_topics"]
        ) / len(rows)
        relative_lift = ((rag_top1 - baseline_top1) / baseline_top1 * 100) if baseline_top1 else 0.0

        return {
            "benchmark": "offline_medicare_retrieval",
            "note": "Offline deterministic benchmark; does not call OpenAI or external Medicare URLs.",
            "documents": ingest.document_count,
            "chunks": ingest.chunk_count,
            "backends": ingest.backends,
            "baseline": "weighted_title_body_lexical_overlap",
            "rag": "HashEmbeddings with FAISS/Chroma/memory retrieval and cosine-style scoring",
            "query_count": len(rows),
            "baseline_top1_accuracy": round(baseline_top1, 4),
            "rag_top1_accuracy": round(rag_top1, 4),
            "rag_top3_accuracy": round(rag_top3, 4),
            "relative_top1_lift_percent": round(relative_lift, 1),
            "rows": rows,
        }


def print_report(result: dict[str, Any]) -> None:
    print("Medical RAG retrieval benchmark")
    print(f"Mode: {result['note']}")
    print(f"Corpus: {result['documents']} docs, {result['chunks']} chunks")
    print(f"Backends: {', '.join(result['backends'])}")
    print(f"Baseline: {result['baseline']}")
    print(f"RAG: {result['rag']}")
    print(
        "Top-1 accuracy: "
        f"baseline {result['baseline_top1_accuracy']:.0%} vs "
        f"RAG {result['rag_top1_accuracy']:.0%}"
    )
    print(f"Top-3 RAG accuracy: {result['rag_top3_accuracy']:.0%}")
    print(f"Relative top-1 lift: {result['relative_top1_lift_percent']:.1f}%")
    print("\nCases:")
    for row in result["rows"]:
        status = "PASS" if row["rag_top1_topic"] == row["expected_topic"] else "FAIL"
        print(
            f"- {status} expected={row['expected_topic']} "
            f"baseline={row['baseline_topic']} rag={row['rag_top1_topic']} "
            f"backend={row['backend']} citation={row['top_citation']}"
        )
    print("\nJSON:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    print_report(run_retrieval_benchmark())
