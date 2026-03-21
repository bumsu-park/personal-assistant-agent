import logging 
from pathlib import Path
from src.config import Config, project_root
from google.auth.transport.requests import Request 
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool 
from datetime import datetime
from zoneinfo import ZoneInfo
from src.services.llm import get_llm_service
from src.utils.gmail_utils import parse_email
from src.models.gmail_models import EmailSummaryOutput

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']

class GmailService: 
    def __init__(self):
        self.creds = None
        self.service = None 
        self.token_path = Path(Config.DATA_DIR) / "gmail_token.json"
        self._authenticate()
        
    def _authenticate(self):
        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing Gmail credentials")
                self.creds.refresh(Request())
            else:
                logger.info("Startning new authentication flow")
                credentials_path = Path(project_root) / Config.GMAIL_CREDENTIALS_PATH
                if not credentials_path.exists():
                    logger.error("No credentials found for gmail service")
                    raise FileNotFoundError(f"Credentials file not found at {credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
                
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
            logger.info(f"Saved new credentials to {self.token_path}")
        self.service = build('gmail', 'v1', credentials=self.creds)
        logger.info("Gmail service initialzed.")
    
    def query_emails(self, q_parameter: str, max_results: int = 50):
        if not self.service:
            logger.error("Gmail service not initialized")
            raise RuntimeError("Gmail Service is not working")
        
        email_items = self.service.users().messages().list(userId='me', q=q_parameter, maxResults=max_results).execute()
        
        emails = []
        
        for item in email_items.get("messages", []):
            full_msg = self.service.users().messages().get(userId='me', id=item['id'], format='full').execute()
            emails.append(full_msg)
            self.mark_as_read(item["id"])
        
        return emails
    
    def mark_as_read(self, email_id) -> None:
        self.service.users().messages().modify(
            userId='me',
            id=email_id, 
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
    
_gmail_service = None
    
def get_gmail_service() -> GmailService:
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService()
    return _gmail_service

@tool
def retrieve_and_summarize_unread_emails(
    query_hours: int = 24,
    max_results: int = 20
): 
    '''
    Retrieve unread emails and summarize the important ones.
    
    Args:
        query_hours: Number of hours back to search for unread emails (default: 24)
        max_results: Maximum number of emails to retrieve (default: 20)
    
    Returns:
        Summary of important emails with action items, filtered to exclude spam and promotions
    '''
    newer_than_parameter = f"newer_than:{query_hours}h"
    query_parameter_list = ["is:unread", newer_than_parameter, "-category:promotions", "-category:social", "-category:updates"]
    query_parameter = " ".join(query_parameter_list)
    
    try: 
        gmail_service = get_gmail_service()
        llm_service = get_llm_service()
        
        llm = llm_service.get_llm()
        llm_with_structure = llm.with_structured_output(EmailSummaryOutput)
        
        
        emails = gmail_service.query_emails(q_parameter=query_parameter, max_results=max_results)
        
        if not emails:
            return f"Found {len(emails)} unread emails."
        
        emails_summary = ""
        for email in emails:
            print(email)
            emails_summary += parse_email(email)
            
        
        prompt = f"""Here are my unread emails from the last {query_hours} hours:
{emails_summary}
IMPORTANT: Be very selective. Only highlight emails that are:
- From real people I know (not companies/marketing)
- Require my direct response or action
- Are time-sensitive (appointments, deadlines, confirmations)
- Don't add any markdown formats. Just make it completely pure string.
IGNORE completely:
- Marketing emails, newsletters, promotions
- Automated notifications (social media, app updates)
- Shipping updates unless there's a problem
- Subscription/service emails
## Important Emails
- [only truly important ones]
## Action Items
- [only things I actually need to do]
If nothing is important, just say "No important emails."
"""
        response = llm_with_structure.invoke(prompt)
        
        return f"""
## Summary
Found {len(emails)} unread emails, {response.spam_count} were spam/promotions.
## Important Emails
{chr(10).join('- ' + e for e in response.important_emails)}
## Action Items
{chr(10).join('- ' + a for a in response.action_items)}
"""
    except Exception as e:
        logger.error(f"Error in retrieve_unread_emails tool: {e}", exc_info=True)
        return f"Error getting emails: {str(e)}" 
    
