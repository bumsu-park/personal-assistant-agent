import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
from src.core.config import Config
from src.core.llm import get_llm_service
from src.plugins.gmail.utils import parse_email
from src.plugins.gmail.models import EmailSummaryOutput

logger = logging.getLogger(__name__)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailService:
    def __init__(self, credentials_path: str | None = None):
        self.creds = None
        self.service = None
        self._credentials_path = credentials_path or Config.GMAIL_CREDENTIALS_PATH
        self.token_path = Path(Config.DATA_DIR) / "gmail_token.json"
        self._authenticate()

    def _authenticate(self):
        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(self.token_path), SCOPES
            )

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing Gmail credentials")
                self.creds.refresh(Request())
            else:
                logger.info("Starting new authentication flow")
                from src.core.config import project_root

                credentials_path = Path(project_root) / self._credentials_path
                if not credentials_path.exists():
                    logger.error("No credentials found for gmail service")
                    raise FileNotFoundError(
                        f"Credentials file not found at {credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            with open(self.token_path, "w") as token:
                token.write(self.creds.to_json())
            logger.info(f"Saved new credentials to {self.token_path}")
        self.service = build("gmail", "v1", credentials=self.creds)
        logger.info("Gmail service initialized.")

    def query_emails(self, q_parameter: str, max_results: int = 50):
        if not self.service:
            logger.error("Gmail service not initialized")
            raise RuntimeError("Gmail Service is not working")

        email_items = (
            self.service.users()
            .messages()
            .list(userId="me", q=q_parameter, maxResults=max_results)
            .execute()
        )

        emails = []

        for item in email_items.get("messages", []):
            full_msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=item["id"], format="full")
                .execute()
            )
            emails.append(full_msg)
            self.mark_as_read(item["id"])

        return emails

    def mark_as_read(self, email_id) -> None:
        self.service.users().messages().modify(
            userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()


def _make_tools(get_service: callable) -> list:
    """Build @tool functions closed over a service getter."""

    @tool
    def retrieve_and_summarize_unread_emails(
        query_hours: int = 24,
        max_results: int = 20,
    ):
        """
        Retrieve unread emails and summarize the important ones.

        Args:
            query_hours: How many hours back to search. Defaults to 24. Use larger values when the user asks for older emails (e.g. 168 for a week, 720 for a month).
            max_results: Maximum number of emails to retrieve (default: 20). Increase if the user wants a thorough scan.

        Returns:
            Summary of important emails with action items, filtered to exclude spam and promotions
        """
        newer_than_parameter = f"newer_than:{query_hours}h"
        query_parameter_list = [
            "is:unread",
            newer_than_parameter,
            "-category:promotions",
        ]
        query_parameter = " ".join(query_parameter_list)

        try:
            gmail_service = get_service()
            llm_service = get_llm_service()

            llm = llm_service.get_llm()
            llm_with_structure = llm.with_structured_output(EmailSummaryOutput)

            emails = gmail_service.query_emails(
                q_parameter=query_parameter, max_results=max_results
            )

            if not emails:
                return f"Found {len(emails)} unread emails."

            emails_summary = ""
            for email in emails:
                emails_summary += parse_email(email)

            prompt = f"""Here are my unread emails from the last {query_hours} hours:
{emails_summary}
Review my emails and surface anything worth my attention. Use your judgment —
prioritize real people, time-sensitive items, and anything requiring action,
but don't be overly strict. When in doubt, include it.

For each email worth surfacing, give me:
- Who it's from
- One sentence on what it's about
- What (if anything) I need to do

Skip obvious noise: marketing blasts, newsletters, automated notifications,
social media pings...

Format each as a clean block, no markdown. If nothing stands out, say "Nothing worth your attention."
"""
            response = llm_with_structure.invoke(prompt)

            if not response.emails:
                return f"Found {len(emails)} unread emails, nothing worth your attention."

            email_blocks = []
            for e in response.emails:
                block = (
                    f"[{e.urgency.upper()}] {e.sender} — {e.subject}\n  {e.summary}"
                )
                if e.action:
                    block += f"\n  Action: {e.action}"
                email_blocks.append(block)

            return (
                f"Found {len(emails)} unread emails, {response.spam_count} skipped as noise.\n\n"
                + "\n\n".join(email_blocks)
            )
        except Exception as e:
            logger.error(f"Error in retrieve_unread_emails tool: {e}", exc_info=True)
            return f"Error getting emails: {str(e)}"

    return [retrieve_and_summarize_unread_emails]
