"""
Centralized application configuration.

Loads values from the environment and performs
basic startup validation.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Settings:
    """Application configuration settings loaded from environment."""

    def __init__(self) -> None:
        # LLM Keys
        self.GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
        self.GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
        self.DEEPSEEK_API_KEY: str | None = os.getenv("DEEPSEEK_API_KEY")
        self.OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
        self.OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
        self.OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
        # Model name is configuration-driven to avoid hardcoded deprecations.
        # Override in .env with GEMINI_MODEL=<model-name> as needed.
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        # Database Settings
        self.MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        self.MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "aiip")

        # Logging & Telemetry
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.ENABLE_JSON_LOGGING: bool = os.getenv("ENABLE_JSON_LOGGING", "false").lower() in ("true", "1", "yes")

        # Crawler Settings
        self.MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
        self.REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

        # Sheets Integration
        self.GOOGLE_SHEETS_CREDENTIALS_PATH: str | None = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "google_sheets_credentials.json" if os.path.exists("google_sheets_credentials.json") else None)
        self.GOOGLE_SHEETS_CREDENTIALS_JSON: str | None = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        self.GOOGLE_SHEET_ID: str | None = os.getenv("GOOGLE_SHEET_ID")
        self.GOOGLE_SHEETS_URL: str | None = os.getenv("GOOGLE_SHEETS_URL")

    def validate(self) -> list[str]:
        """
        Validate configuration settings and return list of warning strings.
        Raises ValueError for critical configuration issues.
        """
        warnings = []

        if not self.GEMINI_API_KEY:
            warnings.append(
                "GEMINI_API_KEY not configured. LLM extraction will be disabled. "
                "Only rule-based extraction strategies will be executed."
            )

        if self.MAX_CONCURRENT_REQUESTS <= 0:
            raise ValueError("MAX_CONCURRENT_REQUESTS must be greater than 0.")

        if self.REQUEST_TIMEOUT <= 0:
            raise ValueError("REQUEST_TIMEOUT must be greater than 0.")

        return warnings

# Instantiate settings singleton
settings = Settings()
