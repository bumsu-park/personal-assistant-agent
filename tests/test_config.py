import os
from unittest.mock import patch

import pytest

from src.core.config import Config


def _cfg_for_validate(tmp_path, **env):
    """Build a Config with env vars set and paths under tmp_path."""
    with patch.dict(os.environ, env, clear=False):
        c = Config("testagent", env_file=None)
    c.DATA_DIR = tmp_path / "data"
    c.QDRANT_DB_PATH = tmp_path / "qdrant"
    c.VECTOR_STORE_DIR = tmp_path / "vectors"
    c.CHECKPOINTS_DIR = tmp_path / "checkpoints"
    c.ALEXA_DATA_DIR = tmp_path / "alexa"
    return c


class TestConfigValidate:
    def test_valid_anthropic(self, tmp_path):
        c = _cfg_for_validate(
            tmp_path,
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="sk-ant-test",
        )
        c.validate()

    def test_valid_openai(self, tmp_path):
        c = _cfg_for_validate(
            tmp_path,
            LLM_PROVIDER="openai",
            OPENAI_API_KEY="sk-test",
        )
        c.validate()

    def test_missing_key_raises(self, tmp_path):
        c = _cfg_for_validate(
            tmp_path,
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="",
        )
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            c.validate()

    def test_unknown_provider_raises(self, tmp_path):
        c = _cfg_for_validate(
            tmp_path,
            LLM_PROVIDER="unknown_provider",
        )
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            c.validate()

    def test_validate_creates_directories(self, tmp_path):
        data_dir = tmp_path / "data"
        c = _cfg_for_validate(
            tmp_path,
            LLM_PROVIDER="openai",
            OPENAI_API_KEY="sk-test",
        )
        c.DATA_DIR = data_dir
        c.QDRANT_DB_PATH = data_dir / "qdrant"
        c.VECTOR_STORE_DIR = data_dir / "vectors"
        c.CHECKPOINTS_DIR = data_dir / "checkpoints"
        c.ALEXA_DATA_DIR = data_dir / "alexa"
        c.validate()
        assert (data_dir / "qdrant").exists()
        assert (data_dir / "vectors").exists()
        assert (data_dir / "checkpoints").exists()
