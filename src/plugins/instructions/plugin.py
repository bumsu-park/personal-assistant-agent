import logging
from pathlib import Path
from typing import Optional
from src.core.plugin import Plugin

logger = logging.getLogger(__name__)


class InstructionsPlugin(Plugin):
    """Loads a markdown instructions file and injects its contents into the system prompt."""

    name = "instructions"

    def __init__(self, instructions_path: Path):
        self._instructions_path = instructions_path
        self._content: str = ""

    async def setup(self) -> None:
        if self._instructions_path.exists():
            self._content = self._instructions_path.read_text(encoding="utf-8")
            logger.info(f"Loaded instructions from {self._instructions_path}")
        else:
            logger.warning(
                f"Instructions file not found at {self._instructions_path}. "
                "Running without custom instructions."
            )

    def tools(self) -> list:
        return []

    def system_prompt(self) -> Optional[str]:
        if self._content:
            return f"## Agent Instructions\n\n{self._content}"
        return None
