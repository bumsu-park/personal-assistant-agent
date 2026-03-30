import pytest
from unittest.mock import patch, MagicMock
from src.core.config import Config


def _build(provider, **extra_config):
    """Call _build_llm with a given provider, mocking the underlying chat class."""
    from src.core.llm import _build_llm

    mock_instance = MagicMock()

    if provider == "anthropic":
        target = "src.core.llm.ChatAnthropic"
        extra = {"ANTHROPIC_API_KEY": "sk-ant-test", "ANTHROPIC_MODEL": "claude-sonnet-4-6"}
    elif provider == "openai":
        target = "src.core.llm.ChatOpenAI"
        extra = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-4o-mini"}
    elif provider == "deepseek":
        target = "src.core.llm.ChatOpenAI"
        extra = {"DEEPSEEK_API_KEY": "ds-test", "DEEPSEEK_MODEL": "deepseek-chat"}
    elif provider == "qwen":
        target = "src.core.llm.ChatOpenAI"
        extra = {"QWEN_API_KEY": "qwen-test", "QWEN_MODEL": "qwen-max"}

    extra.update(extra_config)

    with patch.multiple(Config, **extra):
        # Lazy imports inside _build_llm need patching at the module level
        with patch(f"langchain_anthropic.ChatAnthropic", mock_instance.__class__, create=True):
            with patch(f"langchain_openai.ChatOpenAI", mock_instance.__class__, create=True):
                result = _build_llm(provider)
    return result


class TestBuildLlm:
    def test_anthropic_provider(self):
        from src.core.llm import _build_llm
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.multiple(Config, ANTHROPIC_API_KEY="sk-ant-test", ANTHROPIC_MODEL="claude-sonnet-4-6"):
            with patch("langchain_anthropic.ChatAnthropic", mock_cls):
                _build_llm("anthropic")
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["api_key"] == "sk-ant-test"

    def test_openai_provider(self):
        from src.core.llm import _build_llm
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.multiple(Config, OPENAI_API_KEY="sk-test", OPENAI_MODEL="gpt-4o-mini"):
            with patch("langchain_openai.ChatOpenAI", mock_cls):
                _build_llm("openai")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "gpt-4o-mini"

    def test_deepseek_uses_openai_compat(self):
        from src.core.llm import _build_llm
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.multiple(Config, DEEPSEEK_API_KEY="ds-key", DEEPSEEK_MODEL="deepseek-chat"):
            with patch("langchain_openai.ChatOpenAI", mock_cls):
                _build_llm("deepseek")
        assert "deepseek.com" in mock_cls.call_args.kwargs["base_url"]

    def test_qwen_uses_openai_compat(self):
        from src.core.llm import _build_llm
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.multiple(Config, QWEN_API_KEY="qwen-key", QWEN_MODEL="qwen-max"):
            with patch("langchain_openai.ChatOpenAI", mock_cls):
                _build_llm("qwen")
        assert "aliyuncs.com" in mock_cls.call_args.kwargs["base_url"]

    def test_unknown_provider_raises(self):
        from src.core.llm import _build_llm
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            _build_llm("bogus")


class TestLLMServiceFallback:
    def test_falls_back_when_primary_fails(self):
        from src.core.llm import LLMService

        fallback_instance = MagicMock()
        fallback_cls = MagicMock(return_value=fallback_instance)

        def exploding_build(provider):
            if provider == "anthropic":
                raise RuntimeError("API unreachable")
            return fallback_cls()

        with patch.multiple(
            Config,
            LLM_PROVIDER="anthropic",
            LLM_FALLBACK_PROVIDER="openai",
        ):
            with patch("src.core.llm._build_llm", side_effect=exploding_build):
                svc = LLMService()

        assert svc.get_llm() is fallback_cls.return_value

    def test_raises_when_no_fallback_configured(self):
        from src.core.llm import LLMService

        with patch.multiple(
            Config,
            LLM_PROVIDER="anthropic",
            LLM_FALLBACK_PROVIDER="",
        ):
            with patch("src.core.llm._build_llm", side_effect=RuntimeError("fail")):
                with pytest.raises(RuntimeError, match="fail"):
                    LLMService()
