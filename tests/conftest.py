import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def reset_llm_service():
    """Reset the LLM singleton between tests."""
    import src.core.llm as llm_module
    llm_module._llm_service = None
    yield
    llm_module._llm_service = None
