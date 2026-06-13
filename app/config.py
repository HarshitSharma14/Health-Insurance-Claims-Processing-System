"""Application configuration via environment variables.

Confidence thresholds and scoring weights that are NOT stored in
policy_terms.json live here. Each one has a comment pointing to the
corresponding entry in docs/assumptions.md where the value is justified.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic credentials (kept for reference; extraction now uses Gemini)
    anthropic_api_key: str = "UNSET"

    # Gemini credentials — get free key at aistudio.google.com
    gemini_api_key: str = "UNSET"

    # Policy data
    policy_file_path: str = "policy_terms.json"

    # LLM models
    # Extraction uses gemini-1.5-flash (free tier: 1500 req/day, vision-capable).
    # See docs/assumptions.md — "LLM provider: Gemini Flash".
    extraction_model: str = "gemini-1.5-flash"
    classification_model: str = "gemini-1.5-flash"

    # LLM call guards
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 1  # one retry with backoff per error-handling.md

    # Confidence thresholds — see docs/assumptions.md for justification.
    # Below this score the Decision Agent overrides any policy verdict to MANUAL_REVIEW.
    # Assumption: 0.60 — below 60% overall confidence we cannot make a reliable
    # automated decision (docs/assumptions.md — "MANUAL_REVIEW confidence threshold").
    manual_review_confidence_threshold: float = 0.60

    # Confidence penalty weights applied when extraction degrades.
    # See docs/assumptions.md — "Confidence penalty weights".
    degraded_extraction_penalty: float = 0.30   # per failed extraction document
    partial_extraction_penalty: float = 0.15    # per partially-extracted document
    ambiguous_policy_check_penalty: float = 0.10  # per ambiguous/borderline check


settings = Settings()
