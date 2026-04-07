from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from src.plugins.market_research.models import Prospect, ProspectEmail, ProspectStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name      TEXT NOT NULL,
    website           TEXT UNIQUE,
    contact_name      TEXT,
    industry          TEXT,
    status            TEXT NOT NULL DEFAULT 'new',
    notes             TEXT,
    source            TEXT,
    last_contacted_at TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status  ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_company ON prospects(company_name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS prospect_emails (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    label       TEXT,
    is_primary  INTEGER NOT NULL DEFAULT 0,
    source      TEXT,
    added_at    TEXT NOT NULL,
    UNIQUE(prospect_id, email)
);
CREATE INDEX IF NOT EXISTS idx_emails_prospect ON prospect_emails(prospect_id);

CREATE TABLE IF NOT EXISTS visited_urls (
    url        TEXT PRIMARY KEY,
    visited_at TEXT NOT NULL
);
"""

_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[a-z]{2,}", re.IGNORECASE)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _label_from_email(email: str) -> str | None:
    prefix = email.split("@")[0].lower()
    known = {"info", "sales", "contact", "hello", "support", "admin", "ceo", "founder"}
    return prefix if prefix in known else None


def _row_to_prospect(row: aiosqlite.Row, emails: list[aiosqlite.Row]) -> Prospect:
    email_objs = [
        ProspectEmail(
            id=e["id"],
            prospect_id=e["prospect_id"],
            email=e["email"],
            label=e["label"],
            is_primary=bool(e["is_primary"]),
            source=e["source"],
            added_at=e["added_at"],
        )
        for e in emails
    ]
    return Prospect(
        id=row["id"],
        company_name=row["company_name"],
        website=row["website"],
        contact_name=row["contact_name"],
        industry=row["industry"],
        emails=email_objs,
        status=ProspectStatus(row["status"]),
        notes=row["notes"],
        source=row["source"],
        last_contacted_at=row["last_contacted_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ProspectStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.executescript(_SCHEMA)
            await db.commit()

    # ------------------------------------------------------------------ #
    # Prospects                                                            #
    # ------------------------------------------------------------------ #

    async def add(
        self,
        company_name: str,
        website: str | None = None,
        contact_name: str | None = None,
        industry: str | None = None,
        notes: str | None = None,
        source: str | None = "manual",
    ) -> Prospect:
        now = _now()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                INSERT INTO prospects
                    (company_name, website, contact_name, industry, notes, source,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?)
                """,
                (company_name, website, contact_name, industry, notes, source, now, now),
            )
            await db.commit()
            row = await (
                await db.execute("SELECT * FROM prospects WHERE id=?", (cur.lastrowid,))
            ).fetchone()
        return _row_to_prospect(row, [])

    async def get(self, prospect_id: int) -> Prospect | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,))
            ).fetchone()
            if row is None:
                return None
            emails = await (
                await db.execute(
                    "SELECT * FROM prospect_emails WHERE prospect_id=? ORDER BY is_primary DESC, id ASC",
                    (prospect_id,),
                )
            ).fetchall()
        return _row_to_prospect(row, emails)

    async def list_all(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> list[Prospect]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                rows = await (
                    await db.execute(
                        "SELECT * FROM prospects WHERE status=? ORDER BY updated_at DESC LIMIT ?",
                        (status, limit),
                    )
                ).fetchall()
            else:
                rows = await (
                    await db.execute(
                        "SELECT * FROM prospects ORDER BY updated_at DESC LIMIT ?",
                        (limit,),
                    )
                ).fetchall()

            prospects = []
            for row in rows:
                emails = await (
                    await db.execute(
                        "SELECT * FROM prospect_emails WHERE prospect_id=? ORDER BY is_primary DESC, id ASC",
                        (row["id"],),
                    )
                ).fetchall()
                prospects.append(_row_to_prospect(row, emails))
        return prospects

    async def update(self, prospect_id: int, **fields: Any) -> Prospect:
        allowed = {
            "company_name", "website", "contact_name", "industry",
            "status", "notes", "last_contacted_at",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            p = await self.get(prospect_id)
            if p is None:
                raise ValueError(f"Prospect {prospect_id} not found")
            return p

        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = [*list(updates.values()), prospect_id]
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE prospects SET {set_clause} WHERE id=?", values
            )
            await db.commit()
        p = await self.get(prospect_id)
        if p is None:
            raise ValueError(f"Prospect {prospect_id} not found after update")
        return p

    async def delete(self, prospect_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "DELETE FROM prospects WHERE id=?", (prospect_id,)
            )
            await db.commit()
        return cur.rowcount > 0

    async def summary(self) -> dict[str, int]:
        async with aiosqlite.connect(self._db_path) as db:
            rows = await (
                await db.execute(
                    "SELECT status, COUNT(*) as cnt FROM prospects GROUP BY status"
                )
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    async def website_exists(self, website: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            row = await (
                await db.execute(
                    "SELECT id FROM prospects WHERE website=?", (website,)
                )
            ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    # Emails                                                               #
    # ------------------------------------------------------------------ #

    async def add_email(
        self,
        prospect_id: int,
        email: str,
        source: str = "web_search",
    ) -> ProspectEmail | None:
        """Add an email for a prospect. Returns None if already exists."""
        label = _label_from_email(email)
        now = _now()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            # Check if this is the first email (make it primary)
            count = (
                await (
                    await db.execute(
                        "SELECT COUNT(*) FROM prospect_emails WHERE prospect_id=?",
                        (prospect_id,),
                    )
                ).fetchone()
            )[0]
            is_primary = 1 if count == 0 else 0

            try:
                cur = await db.execute(
                    """
                    INSERT INTO prospect_emails
                        (prospect_id, email, label, is_primary, source, added_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (prospect_id, email, label, is_primary, source, now),
                )
                await db.commit()
                row = await (
                    await db.execute(
                        "SELECT * FROM prospect_emails WHERE id=?", (cur.lastrowid,)
                    )
                ).fetchone()
            except aiosqlite.IntegrityError:
                # Duplicate — already stored
                return None

        return ProspectEmail(
            id=row["id"],
            prospect_id=row["prospect_id"],
            email=row["email"],
            label=row["label"],
            is_primary=bool(row["is_primary"]),
            source=row["source"],
            added_at=row["added_at"],
        )

    async def set_primary_email(self, prospect_id: int, email: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE prospect_emails SET is_primary=0 WHERE prospect_id=?",
                (prospect_id,),
            )
            await db.execute(
                "UPDATE prospect_emails SET is_primary=1 WHERE prospect_id=? AND email=?",
                (prospect_id, email),
            )
            await db.commit()

    # ------------------------------------------------------------------ #
    # Visited URLs                                                         #
    # ------------------------------------------------------------------ #

    async def mark_url_visited(self, url: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO visited_urls (url, visited_at) VALUES (?, ?)",
                (url, _now()),
            )
            await db.commit()

    async def was_url_visited(self, url: str, ttl_days: int = 7) -> bool:
        cutoff = (
            datetime.now(UTC) - timedelta(days=ttl_days)
        ).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            row = await (
                await db.execute(
                    "SELECT visited_at FROM visited_urls WHERE url=? AND visited_at > ?",
                    (url, cutoff),
                )
            ).fetchone()
        return row is not None

    @staticmethod
    def extract_emails(text: str) -> list[str]:
        """Extract all email addresses from a block of text."""
        return list(dict.fromkeys(_EMAIL_RE.findall(text)))
