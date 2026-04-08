from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ProspectStatus(StrEnum):
    NEW = "new"
    RESEARCHING = "researching"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    NOT_INTERESTED = "not_interested"
    CLOSED = "closed"


class ProspectEmail(BaseModel):
    id: int
    prospect_id: int
    email: str
    label: str | None = Field(
        default=None,
        description="Prefix hint, e.g. 'info', 'sales', 'ceo'",
    )
    is_primary: bool = False
    source: str | None = None  # "manual" | "web_search"
    added_at: str


class Prospect(BaseModel):
    id: int
    company_name: str
    website: str | None = None
    contact_name: str | None = None
    industry: str | None = None
    emails: list[ProspectEmail] = Field(default_factory=list)
    status: ProspectStatus = ProspectStatus.NEW
    notes: str | None = None
    source: str | None = None  # "manual" | "web_search"
    last_contacted_at: str | None = None
    created_at: str
    updated_at: str

    @property
    def primary_email(self) -> str | None:
        for e in self.emails:
            if e.is_primary:
                return e.email
        return self.emails[0].email if self.emails else None

    def format_summary(self) -> str:
        email_str = self.primary_email or "no email"
        extras = len(self.emails) - 1
        if extras > 0:
            email_str += f" (+{extras} more)"
        return f"[{self.id}] {self.company_name} | {self.status.value} | {email_str} | {self.website or 'no website'}"

    def format_detail(self) -> str:
        lines = [
            f"ID:           {self.id}",
            f"Company:      {self.company_name}",
            f"Status:       {self.status.value}",
            f"Website:      {self.website or '—'}",
            f"Contact:      {self.contact_name or '—'}",
            f"Industry:     {self.industry or '—'}",
            f"Source:       {self.source or '—'}",
            f"Last contact: {self.last_contacted_at or '—'}",
            f"Notes:        {self.notes or '—'}",
            f"Added:        {self.created_at}",
        ]
        if self.emails:
            lines.append("Emails:")
            for e in self.emails:
                primary = " (primary)" if e.is_primary else ""
                label = f" [{e.label}]" if e.label else ""
                lines.append(f"  • {e.email}{label}{primary}")
        else:
            lines.append("Emails:       none found yet")
        return "\n".join(lines)
