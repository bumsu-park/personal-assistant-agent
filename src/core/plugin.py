from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)

PLUGIN_REGISTRY: dict[str, type[Plugin]] = {}


def register_plugin(cls: type[Plugin]) -> type[Plugin]:
    PLUGIN_REGISTRY[cls.name] = cls
    logger.debug("Registered plugin: %s", cls.name)
    return cls


class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @classmethod
    @abstractmethod
    def from_config(cls, config: Config) -> "Plugin":
        """Construct this plugin from an agent Config."""
        ...

    @abstractmethod
    def tools(self) -> list: ...

    def system_prompt(self) -> str | None:
        """Optional extra system prompt fragment contributed by this plugin."""
        return None

    async def setup(self) -> None:  # noqa: B027
        """Called once before the agent starts. Override for auth, connections, etc."""

    async def teardown(self) -> None:  # noqa: B027
        """Called on shutdown. Override for cleanup."""
