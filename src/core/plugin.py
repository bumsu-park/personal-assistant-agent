from abc import ABC, abstractmethod


class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def tools(self) -> list: ...

    def system_prompt(self) -> str | None:
        """Optional extra system prompt fragment contributed by this plugin."""
        return None

    async def setup(self) -> None:  # noqa: B027
        """Called once before the agent starts. Override for auth, connections, etc."""

    async def teardown(self) -> None:  # noqa: B027
        """Called on shutdown. Override for cleanup."""
