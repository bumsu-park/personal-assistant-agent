from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.plugin import Plugin, register_plugin
from src.plugins.gmail.service import GmailService, _make_tools

if TYPE_CHECKING:
    from src.core.config import Config


@register_plugin
class GmailPlugin(Plugin):
    name = "gmail"

    def __init__(self, config: Config, credentials_path: str | None = None):
        self._config = config
        self._credentials_path = credentials_path
        self._service: GmailService | None = None

    @classmethod
    def from_config(cls, config: Config) -> GmailPlugin:
        return cls(config=config, credentials_path=config.GMAIL_CREDENTIALS_PATH)

    async def setup(self) -> None:
        self._service = GmailService(
            self._config, credentials_path=self._credentials_path
        )

    def tools(self) -> list:
        return _make_tools(lambda: self._service, self._config)
