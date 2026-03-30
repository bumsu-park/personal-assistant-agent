import base64
import logging
from email.mime.text import MIMEText
from pathlib import Path

from src.core.config import Config
from src.plugins.work_gmail.utils import parse_email
from src.plugins.work_gmail.models import EmailSummaryOutput
from src.core.llm import get_llm_service
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


class WorkGmailService:
    def __init__(self, credentials_path: str | None = None):
        self._credentials_path = credentials_path or Config.GMAIL_CREDENTIALS_PATH
        self.token_path = Path(Config.DATA_DIR) / "work_gmail_token.json"
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from src.core.config import project_root

        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(self.token_path), SCOPES
            )
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing WorkGmail credentials")
                self.creds.refresh(Request())
            else:
                credentials_path = Path(project_root) / self._credentials_path
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found at {credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as token:
                token.write(self.creds.to_json())
            logger.info(f"Saved WorkGmail credentials to {self.token_path}")
        self.service = build("gmail", "v1", credentials=self.creds)
        logger.info("WorkGmailService initialized.")

    def query_emails(self, q_parameter: str, max_results: int = 50) -> list:
        items = (
            self.service.users()
            .messages()
            .list(userId="me", q=q_parameter, maxResults=max_results)
            .execute()
        )
        emails = []
        for item in items.get("messages", []):
            full_msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=item["id"], format="full")
                .execute()
            )
            emails.append(full_msg)
            self.mark_as_read(item["id"])
        return emails

    def mark_as_read(self, email_id: str) -> None:
        self.service.users().messages().modify(
            userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def get_email_by_id(self, message_id: str) -> dict:
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def send_email(self, to: str, subject: str, body: str) -> dict:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        logger.info(f"Email sent to {to}, id={result.get('id')}")
        return result

    def reply_to_email(self, thread_id: str, message_id: str, body: str) -> dict:
        original = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Message-ID"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}
        reply_to_addr = headers.get("From", "")
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        orig_msg_id = headers.get("Message-ID", "")

        message = MIMEText(body)
        message["to"] = reply_to_addr
        message["subject"] = subject
        message["In-Reply-To"] = orig_msg_id
        message["References"] = orig_msg_id

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": thread_id})
            .execute()
        )
        logger.info(f"Reply sent in thread {thread_id}, id={result.get('id')}")
        return result

    def list_history(self, start_history_id: str, max_results: int = 20) -> dict:
        return (
            self.service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                maxResults=max_results,
            )
            .execute()
        )

    def setup_gmail_watch(self, project_id: str, topic_name: str) -> dict:
        topic = f"projects/{project_id}/topics/{topic_name}"
        result = (
            self.service.users()
            .watch(userId="me", body={"topicName": topic, "labelIds": ["INBOX"]})
            .execute()
        )
        logger.info(f"Gmail watch set up: {result}")
        return result

    def stop_gmail_watch(self) -> None:
        self.service.users().stop(userId="me").execute()
        logger.info("Gmail watch stopped.")


def _make_tools(get_service: callable) -> list:

    @tool
    def retrieve_and_summarize_unread_emails(
        query_hours: int = 24,
        max_results: int = 20,
    ) -> str:
        """
        Retrieve unread work emails and summarize the important ones.

        Args:
            query_hours: How many hours back to search (default: 24).
            max_results: Maximum number of emails to retrieve (default: 20).

        Returns:
            Summary of important emails with action items.
        """
        query = f"is:unread newer_than:{query_hours}h -category:promotions"
        try:
            svc = get_service()
            llm = get_llm_service().get_llm().with_structured_output(EmailSummaryOutput)
            emails = svc.query_emails(q_parameter=query, max_results=max_results)
            if not emails:
                return "No unread emails found."

            emails_text = "".join(parse_email(e) for e in emails)
            prompt = (
                f"Here are my unread emails from the last {query_hours} hours:\n{emails_text}\n"
                "Surface anything worth my attention — real people, time-sensitive items, action needed. "
                "Skip marketing, newsletters, automated notifications."
            )
            response = llm.invoke(prompt)
            if not response.emails:
                return f"Found {len(emails)} emails, nothing worth your attention."

            blocks = []
            for e in response.emails:
                block = f"[{e.urgency.upper()}] {e.sender} — {e.subject}\n  {e.summary}"
                if e.action:
                    block += f"\n  Action: {e.action}"
                blocks.append(block)
            return (
                f"Found {len(emails)} emails, {response.spam_count} skipped.\n\n"
                + "\n\n".join(blocks)
            )
        except Exception as e:
            logger.error(f"Error in retrieve_and_summarize_unread_emails: {e}", exc_info=True)
            return f"Error getting emails: {str(e)}"

    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """
        Send a new email.

        Args:
            to: Recipient email address
            subject: Email subject line
            body: Plain-text email body

        Returns:
            Confirmation with message ID or error message.
        """
        try:
            result = get_service().send_email(to=to, subject=subject, body=body)
            return f"Email sent. Message ID: {result.get('id')}"
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return f"Error sending email: {str(e)}"

    @tool
    def reply_to_email(thread_id: str, message_id: str, body: str) -> str:
        """
        Reply to an existing email thread.

        Args:
            thread_id: The Gmail thread ID to reply into
            message_id: The message ID being replied to (used to extract reply headers)
            body: Plain-text reply body

        Returns:
            Confirmation with message ID or error message.
        """
        try:
            result = get_service().reply_to_email(
                thread_id=thread_id, message_id=message_id, body=body
            )
            return f"Reply sent. Message ID: {result.get('id')}"
        except Exception as e:
            logger.error(f"Error sending reply: {e}", exc_info=True)
            return f"Error sending reply: {str(e)}"

    return [retrieve_and_summarize_unread_emails, send_email, reply_to_email]
