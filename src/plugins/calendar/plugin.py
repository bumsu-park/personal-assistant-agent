from src.core.plugin import Plugin
from src.plugins.calendar.service import CalendarService, _make_tools


class CalendarPlugin(Plugin):
    name = "calendar"

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._service: CalendarService | None = None

    async def setup(self) -> None:
        self._service = CalendarService(
            username=self._username, password=self._password
        )

    def tools(self) -> list:
        return _make_tools(lambda: self._service)
