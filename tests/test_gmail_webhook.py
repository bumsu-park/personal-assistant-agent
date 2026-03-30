import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents.work import webhook as wh_module
from src.agents.work.webhook import register_webhook_routes
from src.core.config import Config
from src.plugins.work_gmail import WorkGmailPlugin


def make_pubsub_body(history_id="99999", email="user@example.com"):
    data = json.dumps({"emailAddress": email, "historyId": history_id})
    encoded = base64.b64encode(data.encode()).decode()
    return {
        "message": {
            "data": encoded,
            "messageId": "pub1",
            "publishTime": "2026-01-01T00:00:00Z",
        },
        "subscription": "projects/test/subscriptions/gmail-sub",
    }


@pytest.fixture(autouse=True)
def reset_history_id():
    wh_module._last_history_id = None
    yield
    wh_module._last_history_id = None


@pytest.fixture
def mock_graph():
    g = AsyncMock()
    g.ainvoke.return_value = {"messages": [MagicMock(content="done")]}
    return g


@pytest.fixture
def mock_gmail_plugin():
    plugin = MagicMock(spec=WorkGmailPlugin)
    plugin._service = MagicMock()
    plugin._service.list_history.return_value = {"history": []}
    return plugin


@pytest.fixture
def client(mock_graph, mock_gmail_plugin):
    app = FastAPI()
    register_webhook_routes(app, lambda: mock_graph, [mock_gmail_plugin])
    return TestClient(app), mock_graph, mock_gmail_plugin


class TestWebhookTokenVerification:
    def test_wrong_token_returns_403(self, client):
        test_client, _, _ = client
        with patch.object(Config, "GMAIL_PUBSUB_VERIFICATION_TOKEN", "secret"):
            resp = test_client.post(
                "/webhooks/gmail?token=wrong", json=make_pubsub_body()
            )
        assert resp.status_code == 403

    def test_correct_token_returns_200(self, client):
        test_client, _, _ = client
        with patch.object(Config, "GMAIL_PUBSUB_VERIFICATION_TOKEN", "secret"):
            resp = test_client.post(
                "/webhooks/gmail?token=secret", json=make_pubsub_body()
            )
        assert resp.status_code == 200

    def test_no_token_configured_skips_check(self, client):
        test_client, _, _ = client
        with patch.object(Config, "GMAIL_PUBSUB_VERIFICATION_TOKEN", ""):
            resp = test_client.post("/webhooks/gmail", json=make_pubsub_body())
        assert resp.status_code == 200


class TestWebhookProcessing:
    def test_no_new_messages_graph_not_called(self, client):
        test_client, mock_graph, mock_plugin = client
        mock_plugin._service.list_history.return_value = {"history": []}
        resp = test_client.post("/webhooks/gmail", json=make_pubsub_body())
        assert resp.status_code == 200
        mock_graph.ainvoke.assert_not_called()

    def test_new_inbox_unread_message_invokes_graph(self, client):
        test_client, mock_graph, mock_plugin = client
        mock_plugin._service.list_history.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "msg1", "labelIds": ["INBOX", "UNREAD"]}}
                    ]
                }
            ]
        }
        mock_plugin._service.get_email_by_id.return_value = {
            "id": "msg1",
            "threadId": "thread1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Inquiry"},
                    {"name": "Date", "value": "Mon, 01 Jan 2026"},
                ],
                "body": {"data": ""},
                "parts": [],
            },
            "snippet": "I am interested in your services",
        }
        resp = test_client.post("/webhooks/gmail", json=make_pubsub_body())
        assert resp.status_code == 200
        mock_graph.ainvoke.assert_called_once()
        args = mock_graph.ainvoke.call_args[0][0]
        assert args["user_id"] == "webhook_processor"

    def test_sent_message_not_processed(self, client):
        test_client, mock_graph, mock_plugin = client
        mock_plugin._service.list_history.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "msg2", "labelIds": ["SENT"]}}
                    ]
                }
            ]
        }
        resp = test_client.post("/webhooks/gmail", json=make_pubsub_body())
        assert resp.status_code == 200
        mock_graph.ainvoke.assert_not_called()

    def test_malformed_body_returns_200(self, client):
        test_client, mock_graph, _ = client
        resp = test_client.post("/webhooks/gmail", json={"bad": "data"})
        assert resp.status_code == 200
        mock_graph.ainvoke.assert_not_called()

    def test_webhook_prompt_includes_research_instruction(self, client):
        test_client, mock_graph, mock_plugin = client
        mock_plugin._service.list_history.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "msg3", "labelIds": ["INBOX", "UNREAD"]}}
                    ]
                }
            ]
        }
        mock_plugin._service.get_email_by_id.return_value = {
            "id": "msg3",
            "threadId": "t3",
            "payload": {
                "headers": [
                    {"name": "From", "value": "lead@company.com"},
                    {"name": "Subject", "value": "Partnership"},
                    {"name": "Date", "value": "Tue, 02 Jan 2026"},
                ],
                "body": {"data": ""},
                "parts": [],
            },
            "snippet": "Let's work together",
        }
        test_client.post("/webhooks/gmail", json=make_pubsub_body())
        prompt = mock_graph.ainvoke.call_args[0][0]["messages"][0].content
        assert "search_web" in prompt
        assert "reply_to_email" in prompt
