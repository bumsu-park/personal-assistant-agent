import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent

DEFAULT_SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful assistant. Current date and time: {datetime} EST/EDT"
)


class Config:
    def __init__(self, agent_name: str, env_file: str | Path | None = None):
        self.agent_name = agent_name

        if env_file is not None:
            env_path = Path(env_file)
            if not env_path.is_absolute():
                env_path = project_root / env_path
            load_dotenv(env_path, override=True)

        # LLM
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # Telegram Bot (DEPRECATED)
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.ALLOWED_TELEGRAM_USER_IDS = os.getenv(
            "ALLOWED_TELEGRAM_USER_IDS", ""
        ).split(",")

        # Google Calendar Credentials
        self.GOOGLE_CALENDAR_CREDENTIALS_PATH = os.getenv(
            "GOOGLE_CALENDAR_CREDENTIALS_PATH", ""
        )
        self.GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "")

        # CalDAV Credentials
        self.GOOGLE_CALENDAR_EMAIL = os.getenv("GOOGLE_CALENDAR_EMAIL", "")
        self.GOOGLE_APP_PASSWORD = os.getenv("GOOGLE_APP_PASSWORD", "")

        self.ICLOUD_EMAIL = os.getenv("ICLOUD_EMAIL", "")
        self.ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_APP_PASSWORD", "")

        self.AMAZON_EMAIL = os.getenv("AMAZON_EMAIL")
        self.AMAZON_PASSWORD = os.getenv("AMAZON_PASSWORD")
        self.AMAZON_URL = os.getenv("AMAZON_URL", "amazon.com")
        self.AMAZON_OTP = os.getenv("AMAZON_OTP", "")

        # Paths — isolated per agent
        self.DATA_DIR = project_root / "data" / agent_name
        self.VECTOR_STORE_DIR = self.DATA_DIR / "vector_store"
        self.QDRANT_DB_PATH = self.DATA_DIR / "qdrant_db"
        self.CHECKPOINTS_DIR = self.DATA_DIR / "checkpoints"
        self.ALEXA_DATA_DIR = self.DATA_DIR / "alexa"

        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{self.DATA_DIR}/app.db"
        )

        self.MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "50"))
        self.CHECKPOINT_PURGE_DAYS = int(os.getenv("CHECKPOINT_PURGE_DAYS", "7"))
        self.CHECKPOINT_PURGE_INTERVAL_HOURS = int(
            os.getenv("CHECKPOINT_PURGE_INTERVAL_HOURS", "6")
        )

        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # FastAPI
        self.FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
        self.FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
        self.API_KEY = os.getenv("API_KEY", "")

        # System prompt
        self.SYSTEM_PROMPT_TEMPLATE = os.getenv(
            "SYSTEM_PROMPT_TEMPLATE", DEFAULT_SYSTEM_PROMPT_TEMPLATE
        )

    def build_system_prompt(self) -> str:
        now = datetime.now(ZoneInfo("America/New_York")).strftime(
            "%A, %Y-%m-%d %H:%M:%S"
        )
        return self.SYSTEM_PROMPT_TEMPLATE.format(datetime=now)

    def validate(self) -> None:
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in environment variables.")

        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.QDRANT_DB_PATH.mkdir(parents=True, exist_ok=True)
        self.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        self.CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        self.ALEXA_DATA_DIR.mkdir(parents=True, exist_ok=True)
