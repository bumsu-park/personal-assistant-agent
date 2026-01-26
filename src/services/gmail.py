import logging 
from pathlib import Path
from config import Config, project_root
from google.auth.transport.requests import Request 
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

class GmailSerivce: 
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
                credentials_path = Path(project_root) / Config.GOOGLE_CALENDAR_CREDENTIALS_PATH
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
        
        for item in email_items:
            full_msg = self.service.users().messages().get(userId='me', id=item['id'], format='full').execute()
            emails.append(full_msg)
        
        
        
        
        
        
        
        
        
        
        
        
        