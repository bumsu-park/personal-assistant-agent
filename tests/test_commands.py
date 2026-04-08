from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.commands import (
    _commands,
    _sessions,
    command,
    dispatch,
    get_session_thread_id,
)


@pytest.fixture(autouse=True)
def _clean_sessions():
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture
def mock_config():
    return MagicMock()


class TestDispatch:
    @pytest.mark.asyncio
    async def test_non_slash_returns_none(self, mock_config):
        result = await dispatch("hello", thread_id="t1", config=mock_config)
        assert result is None

    @pytest.mark.asyncio
    async def test_unknown_command(self, mock_config):
        result = await dispatch("/foo", thread_id="t1", config=mock_config)
        assert result is not None
        assert "Unknown command: /foo" in result
        assert "/help" in result

    @pytest.mark.asyncio
    async def test_help_lists_commands(self, mock_config):
        result = await dispatch("/help", thread_id="t1", config=mock_config)
        assert "/clear" in result
        assert "/new" in result
        assert "/help" in result

    @pytest.mark.asyncio
    async def test_command_args_parsed(self, mock_config):
        called_with: dict = {}

        @command("_test_echo")
        async def _echo(*, args: str, thread_id: str, config) -> str:
            called_with["args"] = args
            return f"echo: {args}"

        try:
            result = await dispatch("/_test_echo some arg", thread_id="t1", config=mock_config)
            assert result == "echo: some arg"
            assert called_with["args"] == "some arg"
        finally:
            _commands.pop("_test_echo", None)


class TestClearCommand:
    @pytest.mark.asyncio
    async def test_clear_calls_delete_thread(self, mock_config):
        _sessions["t1"] = "abc123"

        with patch("src.core.memory.delete_thread", new_callable=AsyncMock) as mock_delete:
            result = await dispatch("/clear", thread_id="t1", config=mock_config)

        assert result == "Chat history cleared."
        mock_delete.assert_awaited_once_with(mock_config, "t1_abc123")
        assert "t1" not in _sessions

    @pytest.mark.asyncio
    async def test_clear_without_session(self, mock_config):
        with patch("src.core.memory.delete_thread", new_callable=AsyncMock) as mock_delete:
            result = await dispatch("/clear", thread_id="t1", config=mock_config)

        mock_delete.assert_awaited_once_with(mock_config, "t1")
        assert result == "Chat history cleared."


class TestNewCommand:
    @pytest.mark.asyncio
    async def test_new_creates_session(self, mock_config):
        result = await dispatch("/new", thread_id="t1", config=mock_config)
        assert result == "New session started."
        assert "t1" in _sessions
        assert len(_sessions["t1"]) == 8

    @pytest.mark.asyncio
    async def test_new_overwrites_previous_session(self, mock_config):
        _sessions["t1"] = "old"
        await dispatch("/new", thread_id="t1", config=mock_config)
        assert _sessions["t1"] != "old"


class TestGetSessionThreadId:
    def test_no_session_returns_base(self):
        assert get_session_thread_id("t1") == "t1"

    def test_with_session_appends_suffix(self):
        _sessions["t1"] = "abc"
        assert get_session_thread_id("t1") == "t1_abc"
