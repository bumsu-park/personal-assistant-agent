from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)

SlashCommand = Callable[..., Awaitable[str]]

_commands: dict[str, SlashCommand] = {}
_sessions: dict[str, str] = {}


def command(name: str):
    """Decorator to register a slash command."""

    def decorator(fn: SlashCommand) -> SlashCommand:
        _commands[name] = fn
        return fn

    return decorator


async def dispatch(
    message: str, *, thread_id: str, config: Config
) -> str | None:
    """Run a slash command if message starts with `/`, else return None."""
    if not message.startswith("/"):
        return None

    parts = message.strip().split(maxsplit=1)
    name = parts[0][1:]
    args = parts[1] if len(parts) > 1 else ""

    handler = _commands.get(name)
    if handler is None:
        available = ", ".join(f"/{c}" for c in sorted(_commands))
        return f"Unknown command: /{name}. Available: {available}"

    logger.info(f"Slash command: /{name} (thread={thread_id})")
    return await handler(args=args, thread_id=thread_id, config=config)


def get_session_thread_id(base_thread_id: str) -> str:
    """Return the active session thread_id, or the base if no session override."""
    suffix = _sessions.get(base_thread_id)
    if suffix:
        return f"{base_thread_id}_{suffix}"
    return base_thread_id


# --- Built-in commands ---


@command("clear")
async def clear_command(*, args: str, thread_id: str, config: Config) -> str:
    from src.core.memory import delete_thread

    active_thread = get_session_thread_id(thread_id)
    await delete_thread(config, active_thread)
    _sessions.pop(thread_id, None)
    return "Chat history cleared."


@command("new")
async def new_command(*, args: str, thread_id: str, config: Config) -> str:
    session_id = uuid4().hex[:8]
    _sessions[thread_id] = session_id
    return "New session started."


@command("help")
async def help_command(*, args: str, thread_id: str, config: Config) -> str:
    lines = ["Available commands:"]
    for name in sorted(_commands):
        lines.append(f"  /{name}")
    return "\n".join(lines)
