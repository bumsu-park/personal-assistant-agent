from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from src.plugins.market_research.models import ProspectStatus
from src.plugins.market_research.storage import ProspectStore

# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def store(tmp_path: Path) -> ProspectStore:
    s = ProspectStore(tmp_path / "prospects.db")
    await s.initialize()
    return s


# ------------------------------------------------------------------ #
# ProspectStore — CRUD                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_add_and_list_prospect(store: ProspectStore) -> None:
    p = await store.add(company_name="Acme Corp", website="https://acme.com", industry="SaaS")
    assert p.id > 0
    assert p.company_name == "Acme Corp"
    assert p.status == ProspectStatus.NEW

    prospects = await store.list_all()
    assert len(prospects) == 1
    assert prospects[0].company_name == "Acme Corp"


@pytest.mark.asyncio
async def test_update_status(store: ProspectStore) -> None:
    p = await store.add(company_name="Beta Inc")
    updated = await store.update(p.id, status="contacted")
    assert updated.status == ProspectStatus.CONTACTED


@pytest.mark.asyncio
async def test_filter_by_status(store: ProspectStore) -> None:
    await store.add(company_name="Alpha")
    b = await store.add(company_name="Beta")
    await store.update(b.id, status="contacted")

    new_only = await store.list_all(status="new")
    assert len(new_only) == 1
    assert new_only[0].company_name == "Alpha"

    contacted = await store.list_all(status="contacted")
    assert len(contacted) == 1
    assert contacted[0].company_name == "Beta"


@pytest.mark.asyncio
async def test_pipeline_summary(store: ProspectStore) -> None:
    p1 = await store.add(company_name="A")
    p2 = await store.add(company_name="B")
    p3 = await store.add(company_name="C")
    await store.update(p1.id, status="contacted")
    await store.update(p2.id, status="contacted")
    await store.update(p3.id, status="responded")

    summary = await store.summary()
    assert summary["contacted"] == 2
    assert summary["responded"] == 1


@pytest.mark.asyncio
async def test_delete_prospect(store: ProspectStore) -> None:
    p = await store.add(company_name="Gone Corp")
    deleted = await store.delete(p.id)
    assert deleted is True

    result = await store.get(p.id)
    assert result is None


@pytest.mark.asyncio
async def test_delete_nonexistent(store: ProspectStore) -> None:
    deleted = await store.delete(9999)
    assert deleted is False


@pytest.mark.asyncio
async def test_website_deduplication(store: ProspectStore) -> None:
    await store.add(company_name="Dupe Corp", website="https://dupe.com")
    exists = await store.website_exists("https://dupe.com")
    assert exists is True

    exists2 = await store.website_exists("https://other.com")
    assert exists2 is False


# ------------------------------------------------------------------ #
# Emails                                                               #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_add_multiple_emails(store: ProspectStore) -> None:
    p = await store.add(company_name="Email Corp")

    e1 = await store.add_email(p.id, "info@email.com")
    e2 = await store.add_email(p.id, "sales@email.com")
    assert e1 is not None
    assert e2 is not None
    assert e1.is_primary is True   # first email becomes primary
    assert e2.is_primary is False

    full = await store.get(p.id)
    assert len(full.emails) == 2
    assert full.primary_email == "info@email.com"


@pytest.mark.asyncio
async def test_duplicate_email_ignored(store: ProspectStore) -> None:
    p = await store.add(company_name="Dup Email Corp")
    await store.add_email(p.id, "hello@dup.com")
    result = await store.add_email(p.id, "hello@dup.com")
    assert result is None  # duplicate silently ignored

    full = await store.get(p.id)
    assert len(full.emails) == 1


@pytest.mark.asyncio
async def test_set_primary_email(store: ProspectStore) -> None:
    p = await store.add(company_name="Primary Corp")
    await store.add_email(p.id, "info@primary.com")
    await store.add_email(p.id, "ceo@primary.com")

    await store.set_primary_email(p.id, "ceo@primary.com")

    full = await store.get(p.id)
    assert full.primary_email == "ceo@primary.com"


@pytest.mark.asyncio
async def test_email_label_parsed(store: ProspectStore) -> None:
    p = await store.add(company_name="Label Corp")
    e = await store.add_email(p.id, "sales@label.com")
    assert e is not None
    assert e.label == "sales"


# ------------------------------------------------------------------ #
# Visited URLs                                                         #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_visited_url_within_ttl(store: ProspectStore) -> None:
    await store.mark_url_visited("https://example.com")
    assert await store.was_url_visited("https://example.com", ttl_days=7) is True


@pytest.mark.asyncio
async def test_unvisited_url(store: ProspectStore) -> None:
    assert await store.was_url_visited("https://never.com", ttl_days=7) is False


# ------------------------------------------------------------------ #
# Email extraction                                                     #
# ------------------------------------------------------------------ #

def test_extract_emails_from_text() -> None:
    text = "Contact us at hello@acme.com or sales@acme.com for more info."
    emails = ProspectStore.extract_emails(text)
    assert "hello@acme.com" in emails
    assert "sales@acme.com" in emails
    assert len(emails) == 2


def test_extract_emails_deduplicates() -> None:
    text = "hello@acme.com and hello@acme.com again"
    emails = ProspectStore.extract_emails(text)
    assert emails.count("hello@acme.com") == 1


# ------------------------------------------------------------------ #
# Research brief                                                       #
# ------------------------------------------------------------------ #

def test_research_brief_default_created(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from src.plugins.market_research.service import MarketResearchService

    config = MagicMock()
    config.DATA_DIR = tmp_path
    config.TAVILY_API_KEY = ""
    config.EXA_API_KEY = ""
    config.MARKET_RESEARCH_SEARCH_PROVIDER = "tavily"
    config.MARKET_RESEARCH_MAX_RESULTS = 25
    config.MARKET_RESEARCH_URL_TTL_DAYS = 7

    import asyncio

    svc = MarketResearchService(config)
    asyncio.run(svc.setup())

    brief_path = tmp_path / "market_research_brief.md"
    assert brief_path.exists()
    content = brief_path.read_text()
    assert "Ideal Customer Profile" in content


def test_research_brief_update(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from src.plugins.market_research.service import MarketResearchService

    config = MagicMock()
    config.DATA_DIR = tmp_path
    config.TAVILY_API_KEY = ""
    config.EXA_API_KEY = ""
    config.MARKET_RESEARCH_SEARCH_PROVIDER = "tavily"
    config.MARKET_RESEARCH_MAX_RESULTS = 25
    config.MARKET_RESEARCH_URL_TTL_DAYS = 7

    import asyncio

    svc = MarketResearchService(config)
    asyncio.run(svc.setup())
    svc.update_brief("# Custom Brief\n\nSell widgets to factories.")
    assert "widgets" in svc.get_brief()


# ------------------------------------------------------------------ #
# No search provider — graceful degradation                            #
# ------------------------------------------------------------------ #

def test_search_for_prospects_no_provider(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from src.plugins.market_research.service import MarketResearchService

    config = MagicMock()
    config.DATA_DIR = tmp_path
    config.TAVILY_API_KEY = ""
    config.EXA_API_KEY = ""
    config.MARKET_RESEARCH_SEARCH_PROVIDER = "tavily"
    config.MARKET_RESEARCH_MAX_RESULTS = 25
    config.MARKET_RESEARCH_URL_TTL_DAYS = 7

    import asyncio

    svc = MarketResearchService(config)
    asyncio.run(svc.setup())

    result = asyncio.run(svc.search_for_prospects())
    assert "TAVILY_API_KEY" in result or "EXA_API_KEY" in result


def test_find_contact_email_no_provider(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from src.plugins.market_research.service import MarketResearchService

    config = MagicMock()
    config.DATA_DIR = tmp_path
    config.TAVILY_API_KEY = ""
    config.EXA_API_KEY = ""
    config.MARKET_RESEARCH_SEARCH_PROVIDER = "tavily"
    config.MARKET_RESEARCH_MAX_RESULTS = 25
    config.MARKET_RESEARCH_URL_TTL_DAYS = 7

    import asyncio

    svc = MarketResearchService(config)
    asyncio.run(svc.setup())

    # Add a prospect first
    asyncio.run(svc.add_prospect("Test Corp"))
    prospects = asyncio.run(svc._store.list_all())
    result = asyncio.run(svc.find_contact_email(prospects[0].id))
    assert "TAVILY_API_KEY" in result or "EXA_API_KEY" in result
