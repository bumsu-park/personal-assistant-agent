import os 
from pathlib import Path
from dotenv import load_dotenv 

project_root = Path(__file__).parent.parent 
environment = os.getenv("ENVIRONMENT", "dev")
load_dotenv(project_root / f'.env.{environment}')

class Config:
    # LLM 
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Telegram Bot
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
    
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # FastAPI
    FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
    
    @classmethod 
    def validate(cls) -> None:
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in environment variables.")
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables.")
        

        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.QDRANT_DB_PATH.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        cls.CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True) 
        cls.ALEXA_DATA_DIR.mkdir(parents=True, exist_ok=True)