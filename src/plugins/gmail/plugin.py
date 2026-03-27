from src.core.plugin import Plugin
from src.plugins.gmail.service import GmailService, _make_tools


class GmailPlugin(Plugin):
    name = "gmail"

    def __init__(self, credentials_path: str | None = None):
        self._credentials_path = credentials_path
        self._service: GmailService | None = None

    async def setup(self) -> None:
        self._service = GmailService(credentials_path=self._credentials_path)

    def tools(self) -> list:
        return _make_tools(lambda: self._service)
