from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.plugin import Plugin, register_plugin
from src.plugins.calendar.service import CalendarService, _make_tools

if TYPE_CHECKING:
    from src.core.config import Config


@register_plugin
class CalendarPlugin(Plugin):
    name = "calendar"

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._service: CalendarService | None = None

    @classmethod
    def from_config(cls, config: Config) -> CalendarPlugin:
        return cls(
            username=config.ICLOUD_EMAIL,
            password=config.ICLOUD_APP_PASSWORD,
        )

    async def setup(self) -> None:
        self._service = CalendarService(
            username=self._username, password=self._password
        )

    def tools(self) -> list:
        return _make_tools(lambda: self._service)
