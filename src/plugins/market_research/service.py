from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from src.plugins.market_research.storage import ProspectStore

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from src.core.config import Config

logger = logging.getLogger(__name__)

_DEFAULT_BRIEF = """\
# Market Research Brief

## Product
[Describe what you are selling here]

## Ideal Customer Profile
- Industry: [e.g. SaaS, fintech, e-commerce]
- Company size: [e.g. 10-200 employees]
- Geography: [e.g. North America]
- Job titles to target: [e.g. CEO, Head of Operations]

## Good Prospect Signals
- [e.g. recently funded, hiring rapidly, uses competing tools]

## Avoid
- [e.g. enterprises over 1000 employees, non-profits]
"""


class MarketResearchService:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._store = ProspectStore(config.DATA_DIR / "prospects.db")
        self._brief_path: Path = config.DATA_DIR / "market_research_brief.md"
        self._profiles_dir: Path = config.DATA_DIR / "profiles"
        self._searcher: _SearchProvider | None = None

    async def setup(self) -> None:
        await self._store.initialize()
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        if not self._brief_path.exists():
            self._brief_path.write_text(_DEFAULT_BRIEF, encoding="utf-8")
            logger.info("Created default market research brief at %s", self._brief_path)
        self._searcher = _build_searcher(self._config)

    # ------------------------------------------------------------------ #
    # Brief                                                                #
    # ------------------------------------------------------------------ #

    def get_brief(self) -> str:
        return self._brief_path.read_text(encoding="utf-8")

    def update_brief(self, content: str) -> None:
        self._brief_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Prospect CRUD                                                        #
    # ------------------------------------------------------------------ #

    async def add_prospect(
        self,
        company_name: str,
        website: str | None = None,
        contact_name: str | None = None,
        email: str | None = None,
        industry: str | None = None,
        notes: str | None = None,
    ) -> str:
        prospect = await self._store.add(
            company_name=company_name,
            website=website,
            contact_name=contact_name,
            industry=industry,
            notes=notes,
            source="manual",
        )
        if email:
            await self._store.add_email(prospect.id, email, source="manual")
            prospect = await self._store.get(prospect.id)
        return f"Added prospect:\n{prospect.format_detail()}"

    async def list_prospects(self, status: str | None = None, limit: int = 20) -> str:
        prospects = await self._store.list_all(status=status, limit=limit)
        if not prospects:
            msg = "No prospects found"
            if status:
                msg += f" with status '{status}'"
            return msg
        header = f"Prospects ({len(prospects)} shown"
        if status:
            header += f", status={status}"
        header += "):"
        lines = [header] + [p.format_summary() for p in prospects]
        return "\n".join(lines)

    async def get_prospect(self, prospect_id: int) -> str:
        p = await self._store.get(prospect_id)
        if p is None:
            return f"Prospect {prospect_id} not found."
        return p.format_detail()

    async def update_prospect(
        self,
        prospect_id: int,
        status: str | None = None,
        contact_name: str | None = None,
        notes: str | None = None,
        last_contacted_at: str | None = None,
        primary_email: str | None = None,
    ) -> str:
        p = await self._store.get(prospect_id)
        if p is None:
            return f"Prospect {prospect_id} not found."

        await self._store.update(
            prospect_id,
            status=status,
            contact_name=contact_name,
            notes=notes,
            last_contacted_at=last_contacted_at,
        )

        if primary_email:
            await self._store.set_primary_email(prospect_id, primary_email)

        updated = await self._store.get(prospect_id)
        return f"Updated prospect:\n{updated.format_detail()}"

    async def delete_prospect(self, prospect_id: int) -> str:
        ok = await self._store.delete(prospect_id)
        if ok:
            self._delete_profile(prospect_id)
            return f"Prospect {prospect_id} deleted."
        return f"Prospect {prospect_id} not found."

    async def get_pipeline_summary(self) -> str:
        counts = await self._store.summary()
        if not counts:
            return "No prospects in the pipeline yet."
        total = sum(counts.values())
        lines = [f"Pipeline summary ({total} total):"]
        for status in ["new", "researching", "contacted", "responded", "not_interested", "closed"]:
            n = counts.get(status, 0)
            if n:
                lines.append(f"  {status:>14}: {n}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Company Profiles                                                     #
    # ------------------------------------------------------------------ #

    def _profile_path(self, prospect_id: int) -> Path:
        return self._profiles_dir / f"{prospect_id}.md"

    def get_profile(self, prospect_id: int) -> str | None:
        path = self._profile_path(prospect_id)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _write_profile(self, prospect_id: int, content: str) -> Path:
        path = self._profile_path(prospect_id)
        path.write_text(content, encoding="utf-8")
        return path

    def _delete_profile(self, prospect_id: int) -> None:
        path = self._profile_path(prospect_id)
        if path.exists():
            path.unlink()

    async def research_prospect(self, prospect_id: int) -> str:
        """Run web searches on a prospect and synthesize a markdown profile via LLM."""
        if self._searcher is None:
            return "No search provider configured. Set TAVILY_API_KEY or EXA_API_KEY to enable prospect research."

        p = await self._store.get(prospect_id)
        if p is None:
            return f"Prospect {prospect_id} not found."

        queries = [f"{p.company_name} company about"]
        if p.website:
            queries[0] += f" site:{p.website}"
        queries.append(f"{p.company_name} leadership team founders")
        queries.append(f"{p.company_name} news funding 2025 2026")

        all_snippets: list[dict[str, str]] = []
        for q in queries:
            results = await self._searcher.search(q, max_results=5)
            for r in results:
                all_snippets.append(
                    {
                        "url": r.get("url", ""),
                        "title": r.get("title", ""),
                        "content": r.get("content", ""),
                    }
                )

        if not all_snippets:
            return f"No search results found for '{p.company_name}'."

        snippets_text = "\n\n---\n\n".join(
            f"**{s['title']}** ({s['url']})\n{s['content']}" for s in all_snippets if s["content"]
        )

        brief = self.get_brief()
        profile = await self._synthesize_profile(p.company_name, snippets_text, brief)

        self._write_profile(prospect_id, profile)

        if p.status.value == "new":
            await self._store.update(prospect_id, status="researching")

        logger.info("Wrote profile for prospect %d (%s)", prospect_id, p.company_name)
        return profile

    async def _synthesize_profile(self, company_name: str, snippets: str, brief: str) -> str:
        from src.core.llm import create_llm

        llm: BaseChatModel = create_llm(self._config)

        system = (
            "You are a market research analyst. Given raw web search snippets about a company, "
            "produce a clean, structured Markdown company profile. Stick to facts from the snippets; "
            "do not fabricate information. If a section has no data, write 'No information found.'\n\n"
            "Use this template:\n\n"
            f"# {company_name}\n\n"
            f"_Last researched: {datetime.now(UTC).strftime('%Y-%m-%d')}_\n\n"
            "## Overview\n{what they do, size, founding year, HQ location}\n\n"
            "## Products / Services\n{what they sell or offer}\n\n"
            "## Key People\n{leadership, founders, decision makers}\n\n"
            "## Recent News\n{funding rounds, product launches, key hires, partnerships}\n\n"
            "## Fit Assessment\n{how well they match the ideal customer profile below}\n\n"
            "## Sources\n- {url1}\n- {url2}\n\n"
            "---\n\n"
            "### Ideal Customer Profile (for fit assessment):\n\n"
            f"{brief}"
        )

        response = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Raw search snippets:\n\n{snippets}"},
            ]
        )
        return response.content

    # ------------------------------------------------------------------ #
    # Web Research                                                         #
    # ------------------------------------------------------------------ #

    async def search_for_prospects(self, query: str | None = None, max_results: int = 10) -> str:
        if self._searcher is None:
            return (
                "No search provider configured. Set TAVILY_API_KEY or EXA_API_KEY "
                "and MARKET_RESEARCH_SEARCH_PROVIDER in your environment."
            )

        max_results = min(max_results, self._config.MARKET_RESEARCH_MAX_RESULTS)

        if not query:
            return (
                "Please provide a search query. Read the research brief first "
                "(get_research_brief) and craft a targeted query based on the ICP."
            )

        logger.info("Searching for prospects: %s (max=%d)", query, max_results)
        results = await self._searcher.search(query, max_results)

        added = skipped = 0
        for result in results:
            url = result.get("url", "")
            title = result.get("title", url)
            if not url:
                continue
            # Normalise to root domain
            website = _root_url(url)
            if await self._store.website_exists(website):
                skipped += 1
                continue
            company_name = title.split(" - ")[0].split(" | ")[0].strip() or website
            await self._store.add(
                company_name=company_name,
                website=website,
                source="web_search",
            )
            added += 1

        return (
            f"Search complete for '{query}'.\n"
            f"Found {len(results)} results → added {added} new prospect(s), "
            f"skipped {skipped} already known."
        )

    async def find_contact_email(self, prospect_id: int) -> str:
        if self._searcher is None:
            return "No search provider configured. Set TAVILY_API_KEY or EXA_API_KEY to enable email lookup."

        p = await self._store.get(prospect_id)
        if p is None:
            return f"Prospect {prospect_id} not found."

        query = f"{p.company_name} contact email"
        if p.website:
            query += f" site:{p.website}"

        logger.info("Finding email for prospect %d: %s", prospect_id, query)
        results = await self._searcher.search(query, max_results=5)

        found_emails: list[str] = []
        urls_checked = 0

        for result in results:
            if urls_checked >= 3:
                break
            url = result.get("url", "")
            content = result.get("content", "") + " " + result.get("title", "")

            if url and not await self._store.was_url_visited(url, self._config.MARKET_RESEARCH_URL_TTL_DAYS):
                await self._store.mark_url_visited(url)
                urls_checked += 1

            emails = ProspectStore.extract_emails(content)
            for email in emails:
                if email not in found_emails:
                    found_emails.append(email)

        new_count = 0
        for email in found_emails:
            result_obj = await self._store.add_email(prospect_id, email, source="web_search")
            if result_obj is not None:
                new_count += 1

        if not found_emails:
            return f"No email addresses found for '{p.company_name}'. Try adding one manually with update_prospect."

        updated = await self._store.get(prospect_id)
        lines = [
            f"Found {len(found_emails)} email(s) for '{p.company_name}' "
            f"({new_count} new, {len(found_emails) - new_count} already known):"
        ]
        for e in updated.emails:
            primary = " ← primary" if e.is_primary else ""
            lines.append(f"  • {e.email}{primary}")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
# Search provider abstraction                                          #
# ------------------------------------------------------------------ #


class _SearchProvider:
    async def search(self, query: str, max_results: int) -> list[dict]:
        raise NotImplementedError


class _TavilyProvider(_SearchProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int) -> list[dict]:
        from langchain_community.tools.tavily_search import TavilySearchResults

        t = TavilySearchResults(max_results=max_results, tavily_api_key=self._api_key)
        try:
            raw = await asyncio.wait_for(t.ainvoke(query), timeout=10)
            return raw if isinstance(raw, list) else []
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)
            return []


class _ExaProvider(_SearchProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int) -> list[dict]:
        try:
            from exa_py import Exa  # type: ignore[import]

            exa = Exa(api_key=self._api_key)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    exa.search_and_contents,
                    query,
                    num_results=max_results,
                    text=True,
                ),
                timeout=10,
            )
            return [
                {
                    "url": r.url,
                    "title": r.title or "",
                    "content": r.text or "",
                }
                for r in response.results
            ]
        except Exception as exc:
            logger.warning("Exa search failed: %s", exc)
            return []


def _build_searcher(config: Config) -> _SearchProvider | None:
    provider = config.MARKET_RESEARCH_SEARCH_PROVIDER.lower()
    if provider == "exa" and config.EXA_API_KEY:
        logger.info("Using Exa search provider")
        return _ExaProvider(config.EXA_API_KEY)
    if config.TAVILY_API_KEY:
        logger.info("Using Tavily search provider")
        return _TavilyProvider(config.TAVILY_API_KEY)
    if config.EXA_API_KEY:
        logger.info("Falling back to Exa search provider")
        return _ExaProvider(config.EXA_API_KEY)
    logger.warning("No search provider available. Set TAVILY_API_KEY or EXA_API_KEY.")
    return None


def _root_url(url: str) -> str:
    """Strip path/query to get the root domain URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


# ------------------------------------------------------------------ #
# Tool factory                                                         #
# ------------------------------------------------------------------ #


def make_tools(get_service: Callable[[], MarketResearchService], config: Config) -> list:
    def _svc() -> MarketResearchService:
        return get_service()  # type: ignore[operator]

    @tool
    def get_research_brief() -> str:
        """Return the current market research brief (ideal customer profile, product description,
        target industries, and what to avoid). Read this before searching for prospects."""
        return _svc().get_brief()

    @tool
    def update_research_brief(content: str) -> str:
        """Overwrite the market research brief with new content. Use this when the user wants to
        refine their ideal customer profile, product description, or targeting criteria.

        Args:
            content: The full new content for the brief (Markdown).
        """
        _svc().update_brief(content)
        return "Research brief updated successfully."

    @tool
    async def add_prospect(
        company_name: str,
        website: str | None = None,
        contact_name: str | None = None,
        email: str | None = None,
        industry: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Manually add a potential client (prospect) to the pipeline.

        Args:
            company_name: Name of the company.
            website: Company website URL.
            contact_name: Name of the person to contact.
            email: Known contact email address.
            industry: Industry or sector.
            notes: Any additional notes.
        """
        return await _svc().add_prospect(
            company_name=company_name,
            website=website,
            contact_name=contact_name,
            email=email,
            industry=industry,
            notes=notes,
        )

    @tool
    async def search_for_prospects(
        query: str,
        max_results: int = 10,
    ) -> str:
        """Search the web for potential client companies and add them to the prospect list.
        IMPORTANT: Before calling this tool, read the research brief (get_research_brief)
        and craft a targeted search query based on the ICP, industry, geography, and
        product fit. Skips companies already in the list. Requires TAVILY_API_KEY or
        EXA_API_KEY.

        Args:
            query: A targeted web search query derived from the research brief.
            max_results: Number of results to fetch (default 10, max 25).
        """
        return await _svc().search_for_prospects(query=query, max_results=max_results)

    @tool
    async def list_prospects(status: str | None = None, limit: int = 20) -> str:
        """List prospects in the pipeline, optionally filtered by status.

        Args:
            status: Filter by status: new, researching, contacted, responded,
                    not_interested, or closed. Leave empty to show all.
            limit: Maximum number of results (default 20).
        """
        return await _svc().list_prospects(status=status, limit=limit)

    @tool
    async def get_prospect(prospect_id: int) -> str:
        """Get full details for a single prospect including all known email addresses.

        Args:
            prospect_id: The numeric ID of the prospect.
        """
        return await _svc().get_prospect(prospect_id)

    @tool
    async def update_prospect(
        prospect_id: int,
        status: str | None = None,
        contact_name: str | None = None,
        notes: str | None = None,
        last_contacted_at: str | None = None,
        primary_email: str | None = None,
    ) -> str:
        """Update a prospect's outreach status, contact info, or notes.
        Use this after sending an email to mark the prospect as 'contacted'.

        Args:
            prospect_id: The numeric ID of the prospect.
            status: New status: new, researching, contacted, responded,
                    not_interested, or closed.
            contact_name: Update the contact person's name.
            notes: Add or update notes about this prospect.
            last_contacted_at: ISO datetime of when the prospect was last contacted
                               (e.g. '2026-04-07T14:30:00Z').
            primary_email: Set this email address as the primary one to use for outreach.
        """
        return await _svc().update_prospect(
            prospect_id=prospect_id,
            status=status,
            contact_name=contact_name,
            notes=notes,
            last_contacted_at=last_contacted_at,
            primary_email=primary_email,
        )

    @tool
    async def research_prospect(prospect_id: int) -> str:
        """Research a prospect by searching the web and synthesizing a structured company
        profile (overview, products, key people, news, fit assessment). The profile is
        saved as a Markdown file and returned. Requires TAVILY_API_KEY or EXA_API_KEY.

        Args:
            prospect_id: The numeric ID of the prospect to research.
        """
        return await _svc().research_prospect(prospect_id)

    @tool
    def get_prospect_profile(prospect_id: int) -> str:
        """Return the saved Markdown company profile for a prospect, or a message
        if no profile exists yet. Use research_prospect to generate one first.

        Args:
            prospect_id: The numeric ID of the prospect.
        """
        profile = _svc().get_profile(prospect_id)
        if profile is None:
            return f"No profile found for prospect {prospect_id}. Use research_prospect to generate one."
        return profile

    @tool
    async def find_contact_email(prospect_id: int) -> str:
        """Search the web for contact email addresses for a prospect and store all found emails.
        The first email found becomes the primary. Skips URLs already visited recently.
        Requires TAVILY_API_KEY or EXA_API_KEY.

        Args:
            prospect_id: The numeric ID of the prospect to look up.
        """
        return await _svc().find_contact_email(prospect_id)

    @tool
    async def get_pipeline_summary() -> str:
        """Return a count of prospects grouped by outreach status.
        Use this to get an overview of how the sales pipeline is progressing."""
        return await _svc().get_pipeline_summary()

    @tool
    async def delete_prospect(prospect_id: int) -> str:
        """Permanently remove a prospect and all associated emails from the list.

        Args:
            prospect_id: The numeric ID of the prospect to delete.
        """
        return await _svc().delete_prospect(prospect_id)

    return [
        get_research_brief,
        update_research_brief,
        add_prospect,
        search_for_prospects,
        list_prospects,
        get_prospect,
        update_prospect,
        research_prospect,
        get_prospect_profile,
        find_contact_email,
        get_pipeline_summary,
        delete_prospect,
    ]
