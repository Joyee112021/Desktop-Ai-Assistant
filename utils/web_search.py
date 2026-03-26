from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from utils.logging_utils import get_logger


LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


def search_duckduckgo(query: str, max_results: int = 5) -> list[SearchResult]:
    """Run a lightweight DuckDuckGo Lite search and return parsed results."""
    LOGGER.info("Running web search for query: %s", query)
    encoded_query = quote(query)
    request = Request(
        f"https://lite.duckduckgo.com/lite/?q={encoded_query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urlopen(request, timeout=20) as response:
        document = response.read().decode("utf-8", errors="ignore")

    pattern = re.compile(
        r"<a rel=\"nofollow\" href=\"(?P<href>[^\"]+)\" class='result-link'>(?P<title>.*?)</a>.*?"
        r"<td class='result-snippet'>(?P<snippet>.*?)</td>",
        re.DOTALL,
    )

    results: list[SearchResult] = []
    for match in pattern.finditer(document):
        raw_href = html.unescape(match.group("href"))
        title = _strip_html(match.group("title"))
        snippet = _strip_html(match.group("snippet"))
        url = _extract_duckduckgo_redirect(raw_href)
        results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break

    LOGGER.info("Web search for '%s' returned %s result(s).", query, len(results))
    return results


def format_search_results(query: str, results: list[SearchResult]) -> str:
    lines = [f"Web search results for: {query}"]
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   Snippet: {result.snippet}")
    return "\n".join(lines)


def _extract_duckduckgo_redirect(raw_href: str) -> str:
    if raw_href.startswith("//"):
        raw_href = "https:" + raw_href

    parsed = urlparse(raw_href)
    if parsed.netloc.endswith("duckduckgo.com"):
        query = parsed.query
        match = re.search(r"uddg=([^&]+)", query)
        if match:
            return unquote(match.group(1))
    return raw_href


def _strip_html(value: str) -> str:
    value = re.sub(r"<.*?>", "", value)
    return html.unescape(value).strip()
