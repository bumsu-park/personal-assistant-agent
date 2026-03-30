import pytest
from unittest.mock import MagicMock, patch
from src.plugins.web_research.service import WebResearchService, _make_tools

MOCK_DDG_HTML = """
<html><body>
<div class="result">
  <h2 class="result__title">
    <a href="/l/?uddg=https%3A%2F%2Fexample.com&rut=abc">Example Company</a>
  </h2>
  <a class="result__snippet">A great company that builds things</a>
</div>
<div class="result">
  <h2 class="result__title">
    <a href="https://direct.com">Direct Link Co</a>
  </h2>
  <a class="result__snippet">Another good company</a>
</div>
</body></html>
"""


@pytest.fixture
def mock_service():
    return MagicMock(spec=WebResearchService)


@pytest.fixture
def tools(mock_service):
    return _make_tools(lambda: mock_service)


def get_tool(tools_list, name):
    return next(t for t in tools_list if t.name == name)


class TestSearchWebTool:
    def test_returns_formatted_results(self, tools, mock_service):
        mock_service.search.return_value = [
            {"title": "Result 1", "url": "https://r1.com", "snippet": "Snippet 1"},
            {"title": "Result 2", "url": "https://r2.com", "snippet": "Snippet 2"},
        ]
        result = get_tool(tools, "search_web").invoke({"query": "python tips"})
        assert "Result 1" in result
        assert "https://r1.com" in result

    def test_no_results(self, tools, mock_service):
        mock_service.search.return_value = []
        result = get_tool(tools, "search_web").invoke({"query": "xyzzy"})
        assert "No results" in result

    def test_service_error(self, tools, mock_service):
        mock_service.search.side_effect = Exception("Network error")
        result = get_tool(tools, "search_web").invoke({"query": "test"})
        assert "error" in result.lower()


class TestFindPotentialClientsTool:
    def test_returns_formatted_leads(self, tools, mock_service):
        mock_service.find_potential_clients.return_value = [
            {"title": "Acme Corp", "url": "https://acme.com", "snippet": "B2B SaaS"},
        ]
        result = get_tool(tools, "find_potential_clients").invoke(
            {"industry": "SaaS", "keywords": "CRM", "location": "NY"}
        )
        assert "Acme Corp" in result
        mock_service.find_potential_clients.assert_called_once_with(
            industry="SaaS", keywords="CRM", location="NY"
        )

    def test_empty_location_passed_as_none(self, tools, mock_service):
        mock_service.find_potential_clients.return_value = []
        get_tool(tools, "find_potential_clients").invoke(
            {"industry": "Tech", "keywords": "startup", "location": ""}
        )
        mock_service.find_potential_clients.assert_called_once_with(
            industry="Tech", keywords="startup", location=None
        )

    def test_no_leads(self, tools, mock_service):
        mock_service.find_potential_clients.return_value = []
        result = get_tool(tools, "find_potential_clients").invoke(
            {"industry": "X", "keywords": "Y"}
        )
        assert "No leads" in result


class TestWebResearchServiceUnit:
    def test_search_parses_ddg_html(self):
        svc = WebResearchService()
        mock_resp = MagicMock()
        mock_resp.text = MOCK_DDG_HTML
        mock_resp.raise_for_status = MagicMock()

        with patch("src.plugins.web_research.service.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.return_value = mock_resp
            results = svc.search("test query", max_results=5)

        assert len(results) >= 1
        assert results[0]["title"] == "Example Company"
        assert results[0]["url"] == "https://example.com"

    def test_search_returns_empty_on_error(self):
        svc = WebResearchService()
        with patch("src.plugins.web_research.service.httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.side_effect = Exception("Connection refused")
            results = svc.search("test")
        assert results == []
