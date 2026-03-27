from pydantic import BaseModel, Field 
from typing import Literal, Optional

class Email(BaseModel):
    id: str = Field(description="The unique email ID")
    subject: str = Field(description="Email subject line")
    sender: str = Field(description="Sender's email address and name")
    date: str = Field(description="Date and time the email was sent")
    snippet: str = Field(description="Short preview of the email body")
    body: Optional[str] = Field(default=None, description="Full email body content")
    
class EmailSummary(BaseModel):
    sender: str = Field(description="Who the email is from")
    subject: str = Field(description="Email subject line")
    summary: str = Field(description="One to two sentence summary of what it's about")
    category: str = Field(description="Type of email: meeting, request, FYI, billing, personal, etc.")
    urgency: Literal["high", "medium", "low"] = Field(description="high = needs attention today, medium = this week, low = whenever")
    action: Optional[str] = Field(default=None, description="What the user needs to do, if anything")

class EmailSummaryOutput(BaseModel):
    emails: list[EmailSummary] = Field(description="Emails worth the user's attention")
    spam_count: int = Field(description="Number of emails skipped as noise")