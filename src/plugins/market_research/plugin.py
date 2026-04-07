from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.plugin import Plugin, register_plugin
from src.plugins.market_research.service import MarketResearchService, make_tools

if TYPE_CHECKING:
    from src.core.config import Config


@register_plugin
class MarketResearchPlugin(Plugin):
    name = "market_research"

    def __init__(self, config: Config) -> None:
        self._config = config
        self._service: MarketResearchService | None = None

    @classmethod
    def from_config(cls, config: Config) -> MarketResearchPlugin:
        return cls(config=config)

    async def setup(self) -> None:
        self._service = MarketResearchService(self._config)
        await self._service.setup()

    def tools(self) -> list:
        return make_tools(lambda: self._service, self._config)

    def system_prompt(self) -> str | None:
        return (
            "You have access to a market research plugin for managing a prospect pipeline. "
            "Use get_research_brief to understand what kinds of clients to look for before searching. "
            "After emailing a prospect via the Gmail plugin, always call update_prospect to set "
            "their status to 'contacted' and record last_contacted_at."
        )
