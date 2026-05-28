import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import Settings, get_settings
from .medicare_corpus import OFFICIAL_MEDICARE_URLS, OFFLINE_MEDICARE_DOCS
from .schemas import Citation, KnowledgeIngestResponse

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

try:
    from langchain_community.vectorstores import Chroma, FAISS
except Exception:  # pragma: no cover - optional production dependencies
    Chroma = None
    FAISS = None


class HashEmbeddings(Embeddings):
    """Local deterministic embeddings for offline demos and tests."""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]


@dataclass
class RagHit:
    document: Document
    score: float
    backend: str


class MedicalRAGService:
    def __init__(self, settings: Optional[Settings] = None, embeddings: Optional[Embeddings] = None):
        self.settings = settings or get_settings()
        self.embeddings = embeddings or self._build_embeddings()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        self.documents: List[Document] = []
        self.document_vectors: List[List[float]] = []
        self.faiss_index = None
        self.chroma_index = None
        self._default_loaded = False
        os.makedirs(self.settings.faiss_index_dir, exist_ok=True)
        os.makedirs(self.settings.chroma_persist_dir, exist_ok=True)

    def _build_embeddings(self) -> Embeddings:
        api_key = self.settings.embedding_api_key or self.settings.openai_api_key
        if api_key:
            try:
                from langchain_openai import OpenAIEmbeddings

                return OpenAIEmbeddings(
                    model=self.settings.embedding_model,
                    api_key=api_key,
                    base_url=self.settings.embedding_api_base or self.settings.openai_api_base,
                )
            except Exception:
                pass
        return HashEmbeddings()

    def ensure_default_corpus(self) -> None:
        if self._default_loaded or self.documents:
            return
        if self.settings.use_offline_medicare_sample:
            self.ingest_documents(OFFLINE_MEDICARE_DOCS, source_label="offline_sample")
        self._default_loaded = True

    def ingest_offline_sample(self) -> KnowledgeIngestResponse:
        return self.ingest_documents(OFFLINE_MEDICARE_DOCS, source_label="offline_sample")

    def ingest_urls(
        self,
        urls: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeIngestResponse:
        selected_urls = urls or list(OFFICIAL_MEDICARE_URLS)
        try:
            from langchain_community.document_loaders import WebBaseLoader

            loader = WebBaseLoader(selected_urls)
            documents = loader.load()
            for document in documents:
                document.metadata.update(metadata or {})
                document.metadata.setdefault("source_type", "official_url")
                document.metadata.setdefault("topic", "medicare_guideline")
                document.metadata.setdefault("coverage_area", "medicare")
                document.metadata.setdefault("year", 2026)
                document.metadata.setdefault("url", document.metadata.get("source"))
                document.metadata.setdefault("title", document.metadata.get("title") or document.metadata.get("source"))
            return self.ingest_documents(documents, source_label="official_url")
        except Exception as exc:
            return KnowledgeIngestResponse(
                status="error",
                errors=[str(exc)],
                message="Failed to ingest official Medicare URLs.",
            )

    def ingest_documents(self, documents: Iterable[Document], source_label: str) -> KnowledgeIngestResponse:
        source_documents = list(documents)
        if not source_documents:
            return KnowledgeIngestResponse(status="error", errors=["No documents provided."], message="No documents ingested.")

        chunks = self.splitter.split_documents(source_documents)
        for index, chunk in enumerate(chunks):
            chunk.metadata.setdefault("source_type", source_label)
            chunk.metadata.setdefault("topic", "medicare_guideline")
            chunk.metadata.setdefault("coverage_area", "medicare")
            chunk.metadata.setdefault("year", 2026)
            chunk.metadata.setdefault("title", chunk.metadata.get("source") or "Medicare guideline")
            chunk.metadata["chunk_id"] = f"{source_label}-{len(self.documents) + index}"

        self.documents.extend(chunks)
        self.document_vectors.extend(self.embeddings.embed_documents([chunk.page_content for chunk in chunks]))
        backends: List[str] = ["memory"]
        errors: List[str] = []

        if FAISS is not None:
            try:
                self.faiss_index = FAISS.from_documents(self.documents, self.embeddings)
                self.faiss_index.save_local(self.settings.faiss_index_dir)
                backends.append("faiss")
            except Exception as exc:  # pragma: no cover - dependency/platform dependent
                errors.append(f"FAISS unavailable: {exc}")

        if Chroma is not None:
            try:
                self.chroma_index = Chroma.from_documents(
                    self.documents,
                    self.embeddings,
                    collection_name=self.settings.chroma_collection,
                    persist_directory=self.settings.chroma_persist_dir,
                )
                backends.append("chroma")
            except Exception as exc:  # pragma: no cover - dependency/platform dependent
                errors.append(f"Chroma unavailable: {exc}")

        return KnowledgeIngestResponse(
            status="partial" if errors else "success",
            document_count=len(source_documents),
            chunk_count=len(chunks),
            backends=backends,
            errors=errors,
            message=f"Ingested {len(chunks)} Medicare knowledge chunks.",
        )

    def retrieve(
        self,
        query: str,
        metadata_filter: Optional[Dict[str, Any]] = None,
        k: int = 4,
    ) -> List[RagHit]:
        self.ensure_default_corpus()
        hits: List[RagHit] = []
        hits.extend(self._retrieve_faiss(query, metadata_filter, k))
        hits.extend(self._retrieve_chroma(query, metadata_filter, k))
        if not hits:
            hits.extend(self._retrieve_memory(query, metadata_filter, k))

        deduped: Dict[str, RagHit] = {}
        for hit in sorted(hits, key=lambda item: item.score, reverse=True):
            key = hit.document.metadata.get("chunk_id") or hit.document.page_content[:120]
            deduped.setdefault(str(key), hit)
        return list(deduped.values())[:k]

    def citations_from_hits(self, hits: List[RagHit]) -> List[Citation]:
        citations: List[Citation] = []
        seen = set()
        for hit in hits:
            metadata = hit.document.metadata
            key = (metadata.get("title"), metadata.get("url"))
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                Citation(
                    title=str(metadata.get("title") or "Medicare guideline"),
                    url=metadata.get("url") or metadata.get("source"),
                    source_type=str(metadata.get("source_type") or "medicare_guideline"),
                    topic=metadata.get("topic"),
                    coverage_area=metadata.get("coverage_area"),
                    year=metadata.get("year"),
                    score=round(hit.score, 4),
                    backend=hit.backend,
                )
            )
        return citations

    def _retrieve_faiss(self, query: str, metadata_filter: Optional[Dict[str, Any]], k: int) -> List[RagHit]:
        if self.faiss_index is None:
            return []
        try:
            query_k = min(max(k * 3, 8), max(len(self.documents), k))
            results = self.faiss_index.similarity_search_with_score(query, k=query_k)
            return [
                RagHit(document=document, score=self._distance_to_score(score), backend="faiss")
                for document, score in results
                if self._metadata_matches(document.metadata, metadata_filter)
            ][:k]
        except Exception:
            return []

    def _retrieve_chroma(self, query: str, metadata_filter: Optional[Dict[str, Any]], k: int) -> List[RagHit]:
        if self.chroma_index is None:
            return []
        try:
            query_k = min(max(k * 3, 8), max(len(self.documents), k))
            results = self.chroma_index.similarity_search_with_score(query, k=query_k, filter=metadata_filter)
            return [
                RagHit(document=document, score=self._distance_to_score(score), backend="chroma")
                for document, score in results
                if self._metadata_matches(document.metadata, metadata_filter)
            ][:k]
        except Exception:
            return []

    def _retrieve_memory(self, query: str, metadata_filter: Optional[Dict[str, Any]], k: int) -> List[RagHit]:
        query_vector = self.embeddings.embed_query(query)
        scored: List[RagHit] = []
        for document, vector in zip(self.documents, self.document_vectors):
            if not self._metadata_matches(document.metadata, metadata_filter):
                continue
            score = self._cosine(query_vector, vector)
            scored.append(RagHit(document=document, score=score, backend="memory"))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:k]

    @staticmethod
    def _metadata_matches(metadata: Dict[str, Any], metadata_filter: Optional[Dict[str, Any]]) -> bool:
        if not metadata_filter:
            return True
        for key, expected in metadata_filter.items():
            actual = metadata.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _distance_to_score(distance: float) -> float:
        try:
            return 1.0 / (1.0 + abs(float(distance)))
        except Exception:
            return 0.0

    @staticmethod
    def _cosine(left: List[float], right: List[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
        right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
        return numerator / (left_norm * right_norm)
