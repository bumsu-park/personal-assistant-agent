from unittest.mock import MagicMock, patch

import pytest

from src.core.config import Config


def _config(**kwargs) -> Config:
    defaults = {
        "agent_name": "t",
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_MODEL": "claude-sonnet-4-6",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "gpt-4o-mini",
        "DEEPSEEK_API_KEY": "",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "QWEN_API_KEY": "",
        "QWEN_MODEL": "qwen-max",
        "LLM_PROVIDER": "openai",
        "LLM_FALLBACK_PROVIDER": "",
    }
    defaults.update(kwargs)
    m = MagicMock(spec=Config)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestBuildLlm:
    def test_anthropic_provider(self):
        from src.core.llm import _build_llm

        mock_cls = MagicMock(return_value=MagicMock())
        cfg = _config(
            ANTHROPIC_API_KEY="sk-ant-test",
            ANTHROPIC_MODEL="claude-sonnet-4-6",
        )
        with patch("langchain_anthropic.ChatAnthropic", mock_cls):
            _build_llm("anthropic", cfg)
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["api_key"] == "sk-ant-test"

    def test_openai_provider(self):
        from src.core.llm import _build_llm

        mock_cls = MagicMock(return_value=MagicMock())
        cfg = _config(OPENAI_API_KEY="sk-test", OPENAI_MODEL="gpt-4o-mini")
        with patch("langchain_openai.ChatOpenAI", mock_cls):
            _build_llm("openai", cfg)
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "gpt-4o-mini"

    def test_deepseek_uses_openai_compat(self):
        from src.core.llm import _build_llm

        mock_cls = MagicMock(return_value=MagicMock())
        cfg = _config(DEEPSEEK_API_KEY="ds-key", DEEPSEEK_MODEL="deepseek-chat")
        with patch("langchain_openai.ChatOpenAI", mock_cls):
            _build_llm("deepseek", cfg)
        assert "deepseek.com" in mock_cls.call_args.kwargs["base_url"]

    def test_qwen_uses_openai_compat(self):
        from src.core.llm import _build_llm

        mock_cls = MagicMock(return_value=MagicMock())
        cfg = _config(QWEN_API_KEY="qwen-key", QWEN_MODEL="qwen-max")
        with patch("langchain_openai.ChatOpenAI", mock_cls):
            _build_llm("qwen", cfg)
        assert "aliyuncs.com" in mock_cls.call_args.kwargs["base_url"]

    def test_unknown_provider_raises(self):
        from src.core.llm import _build_llm

        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            _build_llm("bogus", _config())


class TestCreateLlmFallback:
    def test_falls_back_when_primary_fails(self):
        from src.core.llm import create_llm

        fallback_instance = MagicMock()
        fallback_cls = MagicMock(return_value=fallback_instance)

        def exploding_build(provider, config):
            if provider == "anthropic":
                raise RuntimeError("API unreachable")
            return fallback_cls()

        cfg = _config(LLM_PROVIDER="anthropic", LLM_FALLBACK_PROVIDER="openai")
        with patch("src.core.llm._build_llm", side_effect=exploding_build):
            llm = create_llm(cfg)

        assert llm is fallback_instance

    def test_raises_when_no_fallback_configured(self):
        from src.core.llm import create_llm

        cfg = _config(LLM_PROVIDER="anthropic", LLM_FALLBACK_PROVIDER="")
        with patch(
            "src.core.llm._build_llm", side_effect=RuntimeError("fail")
        ):
            with pytest.raises(RuntimeError, match="fail"):
                create_llm(cfg)
