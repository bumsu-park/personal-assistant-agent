import logging
from langchain_openai import ChatOpenAI
from src.core.config import Config

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        logger.info("Initializing LLMService")
        self.llm = ChatOpenAI(
            api_key=Config.OPENAI_API_KEY,
            model=Config.OPENAI_MODEL,
            temperature=0.5,
            streaming=True,
        )
        logger.info("LLMService initialized successfully")

    def get_llm(self):
        return self.llm


_llm_service = None


def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
