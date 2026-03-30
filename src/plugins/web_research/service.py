import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_DDGHTML_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; personal-assistant-bot/1.0)"}


class WebResearchService:
    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    def search(self, query: str, max_results: int = 8) -> list[dict]:
        """Search DuckDuckGo. Returns list of {title, url, snippet}."""
        try:
            with httpx.Client(
                headers=_HEADERS, timeout=self._timeout, follow_redirects=True
            ) as client:
                resp = client.post(_DDGHTML_URL, data={"q": query, "b": ""})
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for div in soup.select(".result")[:max_results]:
                title_tag = div.select_one(".result__title a")
                snippet_tag = div.select_one(".result__snippet")
                if not title_tag:
                    continue
                href = title_tag.get("href", "")
                if "uddg=" in href:
                    uddg = parse_qs(urlparse(href).query).get("uddg", [""])
                    href = unquote(uddg[0]) if uddg[0] else href
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "url": href,
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                })
            return results
        except Exception as e:
            logger.error(f"Web search error: {e}", exc_info=True)
            return []

    def find_potential_clients(
        self,
        industry: str,
        keywords: str,
        location: Optional[str] = None,
        max_results: int = 10,
    ) -> list[dict]:
        """Compose a targeted query and return structured lead results."""
        parts = [industry, keywords]
        if location:
            parts.append(location)
        query = " ".join(parts) + " contact OR about OR team"
        return self.search(query=query, max_results=max_results)


def _make_tools(get_service: callable) -> list:

    @tool
    def search_web(query: str, max_results: int = 8) -> str:
        """
        Search the web using DuckDuckGo. No API key required.

        Args:
            query: Search query string
            max_results: Number of results to return (default: 8)

        Returns:
            Numbered list of results with title, URL, and snippet.
        """
        try:
            results = get_service().search(query=query, max_results=max_results)
            if not results:
                return "No results found."
            lines = [
                f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
                for i, r in enumerate(results, 1)
            ]
            return "\n\n".join(lines)
        except Exception as e:
            return f"Search error: {str(e)}"

    @tool
    def find_potential_clients(
        industry: str,
        keywords: str,
        location: str = "",
    ) -> str:
        """
        Find potential business leads by searching for companies in a given industry.

        Args:
            industry: Target industry or sector (e.g. "SaaS", "e-commerce", "healthcare")
            keywords: Keywords describing the ideal client (e.g. "small business payroll")
            location: Optional geographic filter (e.g. "New York", "UK"). Leave blank for global.

        Returns:
            Numbered list of potential leads with company name, URL, and description.
        """
        try:
            results = get_service().find_potential_clients(
                industry=industry,
                keywords=keywords,
                location=location or None,
            )
            if not results:
                return "No leads found."
            lines = [
                f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
                for i, r in enumerate(results, 1)
            ]
            return "\n\n".join(lines)
        except Exception as e:
            return f"Lead search error: {str(e)}"

    return [search_web, find_potential_clients]
