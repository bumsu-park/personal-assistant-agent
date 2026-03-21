from pydantic import BaseModel, Field 
from typing import Optional

class Email(BaseModel):
    id: str = Field(description="The unique email ID")
    subject: str = Field(description="Email subject line")
    sender: str = Field(description="Sender's email address and name")
    date: str = Field(description="Date and time the email was sent")
    snippet: str = Field(description="Short preview of the email body")
    body: Optional[str] = Field(default=None, description="Full email body content")
    
class EmailSummaryOutput(BaseModel):
    important_emails: list[str] = Field(description="Summary of each important email")
    action_items: list[str] = Field(description="Things the user needs to do")
    spam_count: int = Field(description="Number of emails ignored as spam/promotions")