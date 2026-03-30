import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.core.api import create_app
from src.core.config import Config


@pytest.fixture
def mock_graph():
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [MagicMock(content="Hello, how can I help?")]
    }
    return graph


@pytest.fixture
def client(mock_graph):
    async def graph_factory():
        return mock_graph

    app = create_app(graph_factory, title="Test API")
    return TestClient(app), mock_graph


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        test_client, _ = client
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatEndpoint:
    def test_missing_api_key_returns_422(self, client):
        test_client, _ = client
        response = test_client.post("/api/chat", json={"message": "hello"})
        assert response.status_code == 422

    def test_wrong_api_key_returns_401(self, client):
        test_client, _ = client
        with patch.object(Config, "API_KEY", "correct-key"):
            response = test_client.post(
                "/api/chat",
                json={"message": "hello"},
                headers={"x-api-key": "wrong-key"},
            )
        assert response.status_code == 401

    def test_valid_request_returns_response(self, client):
        test_client, mock_graph = client
        with patch.object(Config, "API_KEY", "test-key"):
            response = test_client.post(
                "/api/chat",
                json={"message": "hello", "user_id": "user1"},
                headers={"x-api-key": "test-key"},
            )
        assert response.status_code == 200
        assert response.json()["response"] == "Hello, how can I help?"

    def test_graph_called_with_correct_thread_id(self, client):
        test_client, mock_graph = client
        with patch.object(Config, "API_KEY", "test-key"):
            test_client.post(
                "/api/chat",
                json={"message": "hello", "user_id": "alice"},
                headers={"x-api-key": "test-key"},
            )
        call_config = mock_graph.ainvoke.call_args.kwargs["config"]
        assert "alice" in call_config["configurable"]["thread_id"]
