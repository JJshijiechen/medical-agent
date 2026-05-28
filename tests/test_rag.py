from src.config import Settings
from src.medical_rag import HashEmbeddings, MedicalRAGService


def test_offline_rag_retrieves_medicare_guidance(tmp_path):
    settings = Settings(
        FAISS_INDEX_DIR=str(tmp_path / "faiss"),
        CHROMA_PERSIST_DIR=str(tmp_path / "chroma"),
        USE_OFFLINE_MEDICARE_SAMPLE=True,
    )
    service = MedicalRAGService(settings=settings, embeddings=HashEmbeddings())
    response = service.ingest_offline_sample()

    hits = service.retrieve("Does Medicare Part B cover preventive screening?", metadata_filter={"coverage_area": "part_b"})
    citations = service.citations_from_hits(hits)

    assert response.chunk_count > 0
    assert hits
    assert citations
    assert all(citation.coverage_area == "part_b" for citation in citations)
