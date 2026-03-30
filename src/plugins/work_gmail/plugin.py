from src.core.plugin import Plugin
from src.plugins.work_gmail.service import WorkGmailService, _make_tools


class WorkGmailPlugin(Plugin):
    name = "work_gmail"

    def __init__(self, credentials_path: str | None = None):
        self._credentials_path = credentials_path
        self._service: WorkGmailService | None = None

    async def setup(self) -> None:
        self._service = WorkGmailService(credentials_path=self._credentials_path)

    def tools(self) -> list:
        return _make_tools(lambda: self._service)
