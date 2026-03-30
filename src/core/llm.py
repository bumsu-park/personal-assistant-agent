from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)


def create_llm(config: Config) -> ChatOpenAI:
    logger.info("Creating LLM instance for agent: %s", config.agent_name)
    return ChatOpenAI(
        api_key=config.OPENAI_API_KEY,
        model=config.OPENAI_MODEL,
        temperature=0.5,
        streaming=True,
    )
