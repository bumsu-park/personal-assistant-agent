import logging
from src.core.plugin import Plugin
from src.plugins.web_research.service import WebResearchService, _make_tools

logger = logging.getLogger(__name__)


class WebResearchPlugin(Plugin):
    name = "web_research"

    def __init__(self):
        self._service: WebResearchService | None = None

    async def setup(self) -> None:
        self._service = WebResearchService()
        logger.info("WebResearchPlugin ready.")

    def tools(self) -> list:
        return _make_tools(lambda: self._service)
