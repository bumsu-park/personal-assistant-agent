import logging
from langchain_core.language_models.chat_models import BaseChatModel
from src.core.config import Config

logger = logging.getLogger(__name__)


def _build_llm() -> BaseChatModel:
    provider = Config.LLM_PROVIDER
    logger.info(f"Initializing LLM with provider: {provider}")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=Config.ANTHROPIC_API_KEY,
            model=Config.ANTHROPIC_MODEL,
            temperature=0.5,
            streaming=True,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=Config.OPENAI_API_KEY,
            model=Config.OPENAI_MODEL,
            temperature=0.5,
            streaming=True,
        )

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            model=Config.DEEPSEEK_MODEL,
            base_url="https://api.deepseek.com/v1",
            temperature=0.5,
            streaming=True,
        )

    if provider == "qwen":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=Config.QWEN_API_KEY,
            model=Config.QWEN_MODEL,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.5,
            streaming=True,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


class LLMService:
    def __init__(self):
        self.llm = _build_llm()
        logger.info("LLMService initialized successfully")

    def get_llm(self) -> BaseChatModel:
        return self.llm


_llm_service = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
