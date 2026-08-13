"""Environment-driven configuration.

Every value can be overridden with environment variables so the same codebase
runs in dev (SQLite, mock AI) and production (PostgreSQL, Redis, real model
providers, object storage).
"""
import os


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


class Settings:
    APP_NAME = "CineForge AI Studio"
    APP_VERSION = "0.1.0"

    # --- data ---
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cineforge.db")

    # --- security ---
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production")
    JWT_ALGORITHM = "HS256"
    TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))
    ACCESS_TOKEN_COOKIE = "cineforge_token"

    # --- AI providers (OpenAI-compatible). Leave unset for mock mode. ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Video generation provider abstraction (mock provider built in).
    VIDEO_PROVIDER = os.getenv("VIDEO_PROVIDER", "auto")  # auto | mock | veo-3.1 | runway-gen-4.5 | kling-3.0 | seedance-2.0

    # Frontier provider keys (leave empty to run the procedural renderer).
    VEO_API_KEY = os.getenv("VEO_API_KEY", "")
    RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY", "")
    KLING_API_KEY = os.getenv("KLING_API_KEY", "")
    SEEDANCE_API_KEY = os.getenv("SEEDANCE_API_KEY", "")

    # Audio / TTS
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    OPENAI_AUDIO_VOICE = os.getenv("OPENAI_AUDIO_VOICE", "nova")
    AUDIO_DEFAULTS = {
        "music_style": os.getenv("AUDIO_MUSIC_STYLE", "cinematic orchestral"),
        "sfx_enabled": _bool("AUDIO_SFX_ENABLED", True),
        "tts_provider": os.getenv("TTS_PROVIDER", "edge"),
        "narration_voice": os.getenv("TTS_VOICE", "en-US-AriaNeural"),
    }

    # Media storage
    MEDIA_DIR = os.getenv("MEDIA_DIR", "./media")

    # --- pipeline ---
    PIPELINE_STAGE_SECONDS = float(os.getenv("PIPELINE_STAGE_SECONDS", "0.7"))
    PIPELINE_FAST = _bool("PIPELINE_FAST", True)

    # --- storage ---
    S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
    S3_BUCKET = os.getenv("S3_BUCKET", "cineforge-media")
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")

    # --- limits ---
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "512"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.OPENAI_API_KEY)


settings = Settings()
