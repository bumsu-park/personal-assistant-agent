import pytest
from unittest.mock import MagicMock, patch
from src.plugins.work_gmail.service import WorkGmailService, _make_tools


@pytest.fixture
def mock_service():
    return MagicMock(spec=WorkGmailService)


@pytest.fixture
def tools(mock_service):
    return _make_tools(lambda: mock_service)


def get_tool(tools_list, name):
    return next(t for t in tools_list if t.name == name)


class TestSendEmailTool:
    def test_success(self, tools, mock_service):
        mock_service.send_email.return_value = {"id": "msg123"}
        result = get_tool(tools, "send_email").invoke(
            {"to": "a@b.com", "subject": "Hi", "body": "Hello"}
        )
        assert "msg123" in result
        mock_service.send_email.assert_called_once_with(
            to="a@b.com", subject="Hi", body="Hello"
        )

    def test_service_error_returns_error_string(self, tools, mock_service):
        mock_service.send_email.side_effect = RuntimeError("SMTP error")
        result = get_tool(tools, "send_email").invoke(
            {"to": "a@b.com", "subject": "S", "body": "B"}
        )
        assert "Error" in result


class TestReplyToEmailTool:
    def test_success(self, tools, mock_service):
        mock_service.reply_to_email.return_value = {"id": "reply789"}
        result = get_tool(tools, "reply_to_email").invoke(
            {"thread_id": "t1", "message_id": "m1", "body": "Thanks!"}
        )
        assert "reply789" in result
        mock_service.reply_to_email.assert_called_once_with(
            thread_id="t1", message_id="m1", body="Thanks!"
        )

    def test_service_error_returns_error_string(self, tools, mock_service):
        mock_service.reply_to_email.side_effect = Exception("API error")
        result = get_tool(tools, "reply_to_email").invoke(
            {"thread_id": "t1", "message_id": "m1", "body": "Hi"}
        )
        assert "Error" in result


class TestWorkGmailServiceSendMethod:
    def test_send_email_calls_gmail_api(self):
        svc = object.__new__(WorkGmailService)
        mock_api = MagicMock()
        svc.service = mock_api
        mock_api.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "sent1"
        }
        result = WorkGmailService.send_email(svc, to="a@b.com", subject="Test", body="Hello")
        assert result["id"] == "sent1"
        mock_api.users.return_value.messages.return_value.send.assert_called_once()

    def test_reply_fetches_headers_then_sends(self):
        svc = object.__new__(WorkGmailService)
        mock_api = MagicMock()
        svc.service = mock_api
        mock_api.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Original subject"},
                    {"name": "Message-ID", "value": "<orig@example.com>"},
                ]
            }
        }
        mock_api.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "reply1"
        }
        result = WorkGmailService.reply_to_email(
            svc, thread_id="thread1", message_id="msg1", body="My reply"
        )
        assert result["id"] == "reply1"
        send_call = mock_api.users.return_value.messages.return_value.send.call_args
        assert send_call.kwargs["body"]["threadId"] == "thread1"
