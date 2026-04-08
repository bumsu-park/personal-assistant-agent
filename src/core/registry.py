import logging

from src.core.config import Config
from src.core.graph import create_agent
from src.core.plugin import Plugin

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self):
        self._graphs: dict = {}
        self._configs: dict[str, Config] = {}

    async def register(self, agent_name: str, config: Config, plugins: list[Plugin]) -> None:
        config.validate()
        compiled = await create_agent(plugins=plugins, config=config)
        self._graphs[agent_name] = compiled
        self._configs[agent_name] = config
        logger.info(f"Registered agent: {agent_name}")

    def get(self, agent_name: str):
        if agent_name not in self._graphs:
            raise KeyError(f"Unknown agent: {agent_name}")
        return self._graphs[agent_name]

    @property
    def configs(self) -> dict[str, Config]:
        return dict(self._configs)

    @property
    def agent_names(self) -> list[str]:
        return list(self._graphs.keys())
