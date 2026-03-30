import os 
from pathlib import Path
from dotenv import load_dotenv 

project_root = Path(__file__).parent.parent.parent
environment = os.getenv("ENVIRONMENT", "dev")
load_dotenv(project_root / f'.env.{environment}')

class Config:
    # LLM Provider — one of: anthropic, openai, deepseek, qwen
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
    # Fallback provider if primary is unavailable (optional)
    LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "")

    # Anthropic (Claude)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # DeepSeek (OpenAI-compatible)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Qwen (OpenAI-compatible)
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-max")
    
    # Telegram Bot (DEPRECATED — superseded by FastAPI API, will be removed)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ALLOWED_TELEGRAM_USER_IDS = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",")
    
    # Google Calendar Credentials
    GOOGLE_CALENDAR_CREDENTIALS_PATH = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "")
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "")

    # CalDAV Credentials
    GOOGLE_CALENDAR_EMAIL = os.getenv("GOOGLE_CALENDAR_EMAIL", "")
    GOOGLE_APP_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD", "")
    
    ICLOUD_EMAIL = os.getenv("ICLOUD_EMAIL", "")
    ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_APP_PASSWORD", "")
    
    AMAZON_EMAIL = os.getenv("AMAZON_EMAIL")
    AMAZON_PASSWORD = os.getenv("AMAZON_PASSWORD")
    AMAZON_URL = os.getenv("AMAZON_URL", "amazon.com")
    AMAZON_OTP = os.getenv("AMAZON_OTP", "")
    
    
    # Paths 
    DATA_DIR = project_root / "data" / environment
    VECTOR_STORE_DIR = DATA_DIR / "vector_store"
    QDRANT_DB_PATH = DATA_DIR / "qdrant_db" 
    CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
    ALEXA_DATA_DIR = DATA_DIR / "alexa"
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR}/app.db")
    
    MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "50"))
    CHECKPOINT_PURGE_DAYS = int(os.getenv("CHECKPOINT_PURGE_DAYS", "7"))
    CHECKPOINT_PURGE_INTERVAL_HOURS = int(
        os.getenv("CHECKPOINT_PURGE_INTERVAL_HOURS", "6")
    )
    
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # FastAPI
    FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
    API_KEY = os.getenv("API_KEY", "")
    
    @classmethod
    def validate(cls) -> None:
        required_keys = {
            "anthropic": ("ANTHROPIC_API_KEY", cls.ANTHROPIC_API_KEY),
            "openai": ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            "deepseek": ("DEEPSEEK_API_KEY", cls.DEEPSEEK_API_KEY),
            "qwen": ("QWEN_API_KEY", cls.QWEN_API_KEY),
        }
        if cls.LLM_PROVIDER not in required_keys:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{cls.LLM_PROVIDER}'. "
                f"Choose from: {', '.join(required_keys)}"
            )
        key_name, key_value = required_keys[cls.LLM_PROVIDER]
        if not key_value:
            raise ValueError(f"{key_name} is not set for provider '{cls.LLM_PROVIDER}'.")
        

        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.QDRANT_DB_PATH.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        cls.CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True) 
        cls.ALEXA_DATA_DIR.mkdir(parents=True, exist_ok=True)
