from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)


def _build_llm(provider: str, config: Config) -> BaseChatModel:
    logger.info("Initializing LLM with provider: %s (agent=%s)", provider, config.agent_name)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            api_key=config.ANTHROPIC_API_KEY,
            model=config.ANTHROPIC_MODEL,
            temperature=0.5,
            streaming=True,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            model=config.OPENAI_MODEL,
            temperature=0.5,
            streaming=True,
        )

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            model=config.DEEPSEEK_MODEL,
            base_url="https://api.deepseek.com/v1",
            temperature=0.5,
            streaming=True,
        )

    if provider == "qwen":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=config.QWEN_API_KEY,
            model=config.QWEN_MODEL,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.5,
            streaming=True,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def create_llm(config: Config) -> BaseChatModel:
    provider = config.LLM_PROVIDER
    fallback = config.LLM_FALLBACK_PROVIDER
    try:
        return _build_llm(provider, config)
    except Exception as e:
        if fallback and fallback != provider:
            logger.warning(
                "Primary LLM provider '%s' failed (%s), falling back to '%s'",
                provider,
                e,
                fallback,
            )
            return _build_llm(fallback, config)
        raise
