from abc import ABC, abstractmethod
from typing import Optional


class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def tools(self) -> list: ...

    def system_prompt(self) -> Optional[str]:
        """Optional extra system prompt fragment contributed by this plugin."""
        return None

    async def setup(self) -> None:
        """Called once before the agent starts. Override for auth, connections, etc."""

    async def teardown(self) -> None:
        """Called on shutdown. Override for cleanup."""
