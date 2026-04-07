"""
Stub out heavy external dependencies (Google Auth, CalDAV, etc.) so that
market_research tests can run without the full dependency stack installed.
The gmail and calendar plugins import these at module level; mocking them
here prevents ImportErrors when src/plugins/__init__.py is loaded.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _stub(name: str) -> MagicMock:
    mod = MagicMock()
    mod.__name__ = name
    mod.__path__ = []  # makes it look like a package
    mod.__spec__ = None
    return mod


_STUBS = [
    "google",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.auth.exceptions",
    "google.oauth2",
    "google.oauth2.credentials",
    "google.oauth2.service_account",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "googleapiclient",
    "googleapiclient.discovery",
    "cryptography",
    "caldav",
    "dateparser",
    "langchain_community",
    "langchain_community.tools",
    "langchain_community.tools.tavily_search",
]

for _name in _STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = _stub(_name)
