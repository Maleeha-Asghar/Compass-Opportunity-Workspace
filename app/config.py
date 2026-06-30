from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Compass"
    environment: Literal["local", "test", "production"] = "local"

    mistral_api_key: str | None = Field(default=None, validation_alias="MISTRAL_API_KEY")
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(
        default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_anon_key: str | None = Field(default=None, validation_alias="SUPABASE_ANON_KEY")
    email_enabled: bool = Field(default=True, validation_alias="EMAIL_ENABLED")
    email_provider_api_key: str | None = Field(default=None, validation_alias="EMAIL_PROVIDER_API_KEY")
    email_provider: Literal["resend", "postmark", "smtp"] = Field(default="resend", validation_alias="EMAIL_PROVIDER")
    email_from: str | None = Field(default=None, validation_alias=AliasChoices("EMAIL_USER", "EMAIL_FROM", "ADMIN_EMAIL"))
    smtp_host: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_HOST", "EMAIL_HOST"))
    smtp_port: int = Field(default=465, validation_alias=AliasChoices("SMTP_PORT", "EMAIL_PORT"))
    smtp_username: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_USERNAME", "EMAIL_USER"))
    smtp_password: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_PASSWORD", "EMAIL_PASS"))
    smtp_use_ssl: bool = Field(default=True, validation_alias="SMTP_USE_SSL")
    tesseract_cmd: str | None = Field(default=None, validation_alias="TESSERACT_CMD")

    text_model: str = Field(default="llama-3.1-8b-instant", validation_alias="TEXT_MODEL")
    fast_model: str = Field(default="llama-3.1-8b-instant", validation_alias="FAST_MODEL")
    vision_model: str = Field(default="llama-3.1-8b-instant", validation_alias="VISION_MODEL")
    embed_model: str = Field(default="mistral-embed", validation_alias="EMBED_MODEL")
    extraction_model: str = Field(default="mistral-large-latest", validation_alias="EXTRACTION_MODEL")
    extraction_use_mistral: bool | None = Field(default=None, validation_alias="EXTRACTION_USE_MISTRAL")
    scrape_use_trafilatura: bool = Field(default=True, validation_alias="SCRAPE_USE_TRAFILATURA")
    scrape_playwright_first: bool = Field(default=False, validation_alias="SCRAPE_PLAYWRIGHT_FIRST")
    extraction_skip_deadline_without_dates: bool = Field(
        default=True,
        validation_alias="EXTRACTION_SKIP_DEADLINE_WITHOUT_DATES",
    )

    search_provider: Literal["tavily"] = "tavily"
    tavily_api_key: str | None = Field(default=None, validation_alias="TAVILY_API_KEY")

    http_user_agent: str = "CompassBot/1.0 (+contact@example.com)"
    min_domain_delay_seconds: float = 3.0
    max_scrape_chars: int = 30_000
    poster_bucket: str = "posters"
    document_bucket: str = "documents"
    max_upload_bytes: int = 10 * 1024 * 1024
    search_cache_ttl_hours: int = Field(default=12, validation_alias="SEARCH_CACHE_TTL_HOURS")
    source_cache_ttl_hours: int = Field(default=48, validation_alias="SOURCE_CACHE_TTL_HOURS")
    search_query_limit: int = Field(default=3, validation_alias="SEARCH_QUERY_LIMIT")
    search_candidate_limit: int = Field(default=6, validation_alias="SEARCH_CANDIDATE_LIMIT")
    search_min_results: int = Field(default=3, validation_alias="SEARCH_MIN_RESULTS")
    dynamic_scraping_enabled: bool = Field(default=False, validation_alias="DYNAMIC_SCRAPING_ENABLED")
    robots_timeout_seconds: int = Field(default=3, validation_alias="ROBOTS_TIMEOUT_SECONDS")
    scrape_timeout_seconds: int = Field(default=8, validation_alias="SCRAPE_TIMEOUT_SECONDS")
    related_page_scraping_enabled: bool = Field(default=True, validation_alias="RELATED_PAGE_SCRAPING_ENABLED")
    max_related_pages_per_source: int = Field(default=3, validation_alias="MAX_RELATED_PAGES_PER_SOURCE")
    tavily_extract_enabled: bool = Field(default=True, validation_alias="TAVILY_EXTRACT_ENABLED")
    tavily_extract_depth: Literal["basic", "advanced"] = Field(default="basic", validation_alias="TAVILY_EXTRACT_DEPTH")
    tavily_extract_chunks_per_source: int = Field(default=3, validation_alias="TAVILY_EXTRACT_CHUNKS_PER_SOURCE")
    tavily_extract_query: str = Field(
        default="application deadline eligibility requirements funding required documents how to apply",
        validation_alias="TAVILY_EXTRACT_QUERY",
    )
    embeddings_enabled: bool = Field(default=False, validation_alias="EMBEDDINGS_ENABLED")
    search_job_timeout_seconds: int = Field(default=240, validation_alias="SEARCH_JOB_TIMEOUT_SECONDS")
    search_planning_timeout_seconds: int = Field(default=45, validation_alias="SEARCH_PLANNING_TIMEOUT_SECONDS")
    search_planning_max_retries: int = Field(default=1, validation_alias="SEARCH_PLANNING_MAX_RETRIES")
    search_extraction_timeout_seconds: int = Field(default=45, validation_alias="SEARCH_EXTRACTION_TIMEOUT_SECONDS")
    search_extraction_max_retries: int = Field(default=1, validation_alias="SEARCH_EXTRACTION_MAX_RETRIES")
    extraction_max_source_chars: int = Field(default=2000, validation_alias="EXTRACTION_MAX_SOURCE_CHARS")
    extraction_max_snippet_chars: int = Field(default=350, validation_alias="EXTRACTION_MAX_SNIPPET_CHARS")
    groq_max_input_chars: int = Field(default=4500, validation_alias="GROQ_MAX_INPUT_CHARS")
    search_extraction_pause_seconds: float = Field(default=1.0, validation_alias="SEARCH_EXTRACTION_PAUSE_SECONDS")
    search_extraction_step_pause_seconds: float = Field(default=1.5, validation_alias="SEARCH_EXTRACTION_STEP_PAUSE_SECONDS")
    search_job_auto_dispatch: bool | None = Field(default=None, validation_alias="SEARCH_JOB_AUTO_DISPATCH")
    reminder_auto_dispatch: bool | None = Field(default=None, validation_alias="REMINDER_AUTO_DISPATCH")
    reminder_poll_seconds: int = Field(default=3600, validation_alias="REMINDER_POLL_SECONDS")
    max_model_retries: int = Field(default=6, validation_alias="MAX_MODEL_RETRIES")
    model_timeout_seconds: int = Field(default=90, validation_alias="MODEL_TIMEOUT_SECONDS")
    max_parallel_model_calls: int = Field(default=2, validation_alias="MAX_PARALLEL_MODEL_CALLS")
    cors_allowed_origins: str = Field(default="", validation_alias="CORS_ALLOWED_ORIGINS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.mistral_api_key)

    @property
    def extraction_prefers_mistral(self) -> bool:
        if self.extraction_use_mistral is not None:
            return self.extraction_use_mistral
        return bool(self.mistral_api_key)

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def auto_dispatch_search_jobs(self) -> bool:
        if self.search_job_auto_dispatch is not None:
            return self.search_job_auto_dispatch
        return self.environment == "local"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.email_from and self.smtp_host and self.smtp_username and self.smtp_password)

    @property
    def effective_email_provider(self) -> Literal["resend", "postmark", "smtp"]:
        if self.smtp_host or self.smtp_username or self.smtp_password:
            return "smtp"
        return self.email_provider

    @property
    def smtp_uses_ssl(self) -> bool:
        if self.smtp_port == 587:
            return False
        return self.smtp_use_ssl

    @property
    def email_configured(self) -> bool:
        if not self.email_enabled:
            return False
        if self.effective_email_provider == "smtp":
            return self.smtp_configured
        return bool(self.email_provider_api_key and self.email_from)

    @property
    def auto_dispatch_reminders(self) -> bool:
        if self.reminder_auto_dispatch is not None:
            return self.reminder_auto_dispatch
        return self.environment == "local" and self.email_configured

    @property
    def allowed_cors_origins(self) -> list[str]:
        configured = [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        local = ["http://127.0.0.1:5173", "http://localhost:5173"]
        return [*local, *configured]

    def is_allowed_cors_origin(self, origin: str | None) -> bool:
        if not origin:
            return False
        normalized = origin.rstrip("/")
        if normalized in self.allowed_cors_origins:
            return True
        return normalized.startswith("http://127.0.0.1:") or normalized.startswith("http://localhost:")

    def require_mistral(self) -> str:
        if not self.mistral_api_key:
            raise RuntimeError("MISTRAL_API_KEY is required.")
        return self.mistral_api_key

    def require_groq(self) -> str:
        if not self.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required.")
        return self.groq_api_key

    def require_tavily(self) -> str:
        if not self.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is required for web search.")
        return self.tavily_api_key

    def require_supabase(self) -> tuple[str, str]:
        if not self.supabase_url or not self.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
        return self.supabase_url, self.supabase_service_role_key

    def require_email(self) -> tuple[str, str]:
        if not self.email_enabled:
            raise RuntimeError("EMAIL_ENABLED is false.")
        if self.effective_email_provider == "smtp":
            if not self.smtp_configured:
                raise RuntimeError("EMAIL_FROM/EMAIL_USER, EMAIL_HOST, EMAIL_USER, and EMAIL_PASS are required for SMTP.")
            return self.smtp_password, self.email_from
        if not self.email_provider_api_key or not self.email_from:
            raise RuntimeError("EMAIL_PROVIDER_API_KEY and EMAIL_FROM are required for email reminders.")
        return self.email_provider_api_key, self.email_from


@lru_cache
def get_settings() -> Settings:
    return Settings()
