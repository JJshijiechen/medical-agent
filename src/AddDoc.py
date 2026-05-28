from typing import List, Optional

from langchain_core.documents import Document

from .config import get_settings
from .medical_rag import MedicalRAGService


class DocumentProcessor:
    """Backward-compatible document processor backed by MedicalRAGService."""

    def __init__(
        self,
        collection_name: str | None = None,
        embedding_model: str | None = None,
        chunk_size: int = 800,
        chunk_overlap: int = 50,
        persist_directory: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        if persist_directory:
            settings.chroma_persist_dir = persist_directory
        settings.chunk_size = chunk_size
        settings.chunk_overlap = chunk_overlap
        self.service = MedicalRAGService(settings=settings)

    async def add_urls(self, urls: List[str]) -> dict:
        return self.service.ingest_urls(urls=urls).model_dump()

    async def _process_documents(self, docs: List[Document]) -> dict:
        return self.service.ingest_documents(docs, source_label="legacy_document_processor").model_dump()
