from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi-source Product Agent (strict)"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    request_timeout_seconds: float = 25.0
    browser_timeout_ms: int = 30000
    max_concurrency: int = 5
    max_candidate_urls_per_source: int = 5
    max_download_bytes: int = 50_000_000
    max_dataset_hits: int = 12
    llm_snippet_chars: int = 5000
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')


settings = Settings()
