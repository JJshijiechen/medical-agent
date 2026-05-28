from .config import get_settings
from .medical_rag import MedicalRAGService


def init_vector_store(use_official_urls: bool = False):
    settings = get_settings()
    service = MedicalRAGService(settings)
    responses = [service.ingest_offline_sample()]
    if use_official_urls:
        responses.append(service.ingest_urls(settings.medicare_guideline_urls))
    for response in responses:
        print(response.model_dump())
    return responses


if __name__ == "__main__":
    init_vector_store()
