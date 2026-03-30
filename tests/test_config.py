import pytest
from unittest.mock import patch
from src.core.config import Config


def _patch_config(**kwargs):
    """Patch multiple Config class attributes at once."""
    return patch.multiple(Config, **kwargs)


class TestConfigValidate:
    def test_valid_anthropic(self, tmp_path):
        with _patch_config(
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="sk-ant-test",
            DATA_DIR=tmp_path / "data",
            QDRANT_DB_PATH=tmp_path / "qdrant",
            VECTOR_STORE_DIR=tmp_path / "vectors",
            CHECKPOINTS_DIR=tmp_path / "checkpoints",
            ALEXA_DATA_DIR=tmp_path / "alexa",
        ):
            Config.validate()  # should not raise

    def test_valid_openai(self, tmp_path):
        with _patch_config(
            LLM_PROVIDER="openai",
            OPENAI_API_KEY="sk-test",
            DATA_DIR=tmp_path / "data",
            QDRANT_DB_PATH=tmp_path / "qdrant",
            VECTOR_STORE_DIR=tmp_path / "vectors",
            CHECKPOINTS_DIR=tmp_path / "checkpoints",
            ALEXA_DATA_DIR=tmp_path / "alexa",
        ):
            Config.validate()

    def test_missing_key_raises(self, tmp_path):
        with _patch_config(
            LLM_PROVIDER="anthropic",
            ANTHROPIC_API_KEY="",
            DATA_DIR=tmp_path / "data",
            QDRANT_DB_PATH=tmp_path / "qdrant",
            VECTOR_STORE_DIR=tmp_path / "vectors",
            CHECKPOINTS_DIR=tmp_path / "checkpoints",
            ALEXA_DATA_DIR=tmp_path / "alexa",
        ):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                Config.validate()

    def test_unknown_provider_raises(self, tmp_path):
        with _patch_config(
            LLM_PROVIDER="unknown_provider",
            DATA_DIR=tmp_path / "data",
            QDRANT_DB_PATH=tmp_path / "qdrant",
            VECTOR_STORE_DIR=tmp_path / "vectors",
            CHECKPOINTS_DIR=tmp_path / "checkpoints",
            ALEXA_DATA_DIR=tmp_path / "alexa",
        ):
            with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
                Config.validate()

    def test_validate_creates_directories(self, tmp_path):
        data_dir = tmp_path / "data"
        with _patch_config(
            LLM_PROVIDER="openai",
            OPENAI_API_KEY="sk-test",
            DATA_DIR=data_dir,
            QDRANT_DB_PATH=data_dir / "qdrant",
            VECTOR_STORE_DIR=data_dir / "vectors",
            CHECKPOINTS_DIR=data_dir / "checkpoints",
            ALEXA_DATA_DIR=data_dir / "alexa",
        ):
            Config.validate()
            assert (data_dir / "qdrant").exists()
            assert (data_dir / "vectors").exists()
            assert (data_dir / "checkpoints").exists()
