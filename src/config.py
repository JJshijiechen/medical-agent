from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_MEDICARE_GUIDELINE_URLS = [
    "https://www.cms.gov/medicare/coverage/preventive-services-coverage",
    "https://www.medicare.gov/coverage/preventive-screening-services?linkId=134567254",
    "https://www.medicare.gov/what-medicare-covers/what-part-b-covers",
    "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/ncd103c1_part1.pdf",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Patient-Centric Medical Agent"
    base_model: str = Field(default="gpt-4o-mini", alias="BASE_MODEL")
    backup_model: str = Field(default="gpt-4o-mini", alias="BACKUP_MODEL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_api_base: str | None = Field(default=None, alias="OPENAI_API_BASE")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_api_key: str | None = Field(default=None, alias="EMBEDDING_API_KEY")
    embedding_api_base: str | None = Field(default=None, alias="EMBEDDING_API_BASE")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    memory_key: str = Field(default="chat_history", alias="MEMORY_KEY")

    slack_bot_token: str | None = Field(default=None, alias="SLACK_BOT_TOKEN")
    slack_app_token: str | None = Field(default=None, alias="SLACK_APP_TOKEN")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")

    google_calendar_id: str = Field(default="primary", alias="GOOGLE_CALENDAR_ID")
    default_timezone: str = Field(default="America/Chicago", alias="DEFAULT_TIMEZONE")

    faiss_index_dir: str = Field(default="./vector_db/faiss", alias="FAISS_INDEX_DIR")
    chroma_persist_dir: str = Field(default="./vector_db/chroma", alias="CHROMA_PERSIST_DIR")
    chroma_collection: str = Field(default="medicare_guidelines", alias="CHROMA_COLLECTION")
    chunk_size: int = Field(default=800, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")
    use_offline_medicare_sample: bool = Field(default=True, alias="USE_OFFLINE_MEDICARE_SAMPLE")
    medicare_guideline_urls: List[str] = Field(
        default_factory=lambda: list(DEFAULT_MEDICARE_GUIDELINE_URLS),
        alias="MEDICARE_GUIDELINE_URLS",
    )

    @field_validator("medicare_guideline_urls", mode="before")
    @classmethod
    def parse_guideline_urls(cls, value):
        if value is None or value == "":
            return list(DEFAULT_MEDICARE_GUIDELINE_URLS)
        if isinstance(value, str):
            normalized = value.replace("\n", ",")
            return [item.strip() for item in normalized.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
