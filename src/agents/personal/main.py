from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.config import Config
from src.plugins.calendar import CalendarPlugin
from src.plugins.gmail import GmailPlugin

if TYPE_CHECKING:
    from src.core.registry import AgentRegistry

AGENT_NAME = "personal"

config = Config(AGENT_NAME, env_file=".env.personal")

PLUGINS = [
    CalendarPlugin(
        username=config.ICLOUD_EMAIL,
        password=config.ICLOUD_APP_PASSWORD,
    ),
    GmailPlugin(
        credentials_path=config.GMAIL_CREDENTIALS_PATH,
    ),
]


async def register(registry: AgentRegistry) -> None:
    await registry.register(AGENT_NAME, config, PLUGINS)
