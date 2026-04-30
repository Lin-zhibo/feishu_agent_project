"""
Web search and fetch tools.

Implements WebSearch (DuckDuckGo HTML API) and WebFetch (URL to markdown).
"""

from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any

import requests
from langchain_core.tools import tool

_log = logging.getLogger("tools.web_tools")


def _parse_duckduckgo_html(html: str) -> list[dict[str, Any]]:
    """
    Parse DuckDuckGo HTML search results.

    Args:
        html: Raw HTML from DuckDuckGo search.

    Returns:
        List of dicts with title, url, snippet keys.
    """
    results: list[dict[str, Any]] = []
    result_pattern = re.compile(
        r'<a class="result__a" href="(?P<url>[^"]+)">(?P<title>[^<]+)</a>.*?'
        r'<a class="result__snippet"[^>]*>(?P<snippet>[^<]+)</a>',
        re.DOTALL,
    )
    for match in result_pattern.finditer(html):
        title = match.group("title").strip()
        url = match.group("url").strip()
        snippet = match.group("snippet").strip()
        snippet = re.sub(r'<[^>]+>', '', snippet)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= 10:
            break
    return results


@tool
def WebSearch(query: str) -> str:
    """
    Search the web for information using DuckDuckGo.

    Args:
        query: The search query to look up.

    Returns:
        JSON string of search results with title, URL, and snippet.
        Returns an empty list if no results are found.
    """
    _log.info("WebSearch called: query=%s", query)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DevFlow/1.0)"}
    params = {"q": query, "kl": "en-us"}
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        _log.warning("WebSearch: request failed: %s", e)
        return json.dumps([{"error": str(e)}], indent=2)

    results = _parse_duckduckgo_html(resp.text)
    _log.info("WebSearch: done, results_count=%d", len(results))
    return json.dumps(results, indent=2, ensure_ascii=False)


@tool
def WebFetch(url: str, max_chars: int = 10000) -> str:
    """
    Fetch content from a URL and convert it to markdown.

    Args:
        url: The fully-formed URL to fetch.
        max_chars: Maximum characters to fetch (default 10000).

    Returns:
        Markdown-formatted content extracted from the URL.
    """
    _log.info("WebFetch called: url=%s, max_chars=%d", url, max_chars)
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DevFlow/1.0)"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        _log.warning("WebFetch: request failed: %s", e)
        return f"Error fetching URL: {e}"

    content = resp.text[:max_chars]

    md_lines: list[str] = []
    lines = content.split("\n")
    in_code_block = False
    code_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if "<code>" in stripped or "<pre>" in stripped:
            in_code_block = True
            code_lines = []
            continue
        if "</code>" in stripped or "</pre>" in stripped:
            in_code_block = False
            md_lines.append("```")
            md_lines.extend(code_lines)
            md_lines.append("```")
            continue
        if in_code_block:
            code_lines.append(stripped)
            continue

        h_match = re.match(r"<h([1-6])[^>]*>(.+)</h\1>", stripped, re.IGNORECASE)
        if h_match:
            level = int(h_match.group(1))
            md_lines.append(f"{'#' * level} {h_match.group(2)}")
            continue

        link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.+?)</a>', re.IGNORECASE)
        def replace_link(m: re.Match) -> str:
            href = m.group(1)
            text = m.group(2)
            return f"[{text}]({href})"
        line = link_pattern.sub(replace_link, line)

        if re.match(r"<p[^>]*>", stripped, re.IGNORECASE):
            continue
        if stripped == "" or stripped == "<br>" or stripped == "<br/>":
            md_lines.append("")
            continue

        li_match = re.match(r"<li[^>]*>(.+)</li>", stripped, re.IGNORECASE)
        if li_match:
            md_lines.append(f"- {li_match.group(1)}")
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = line.replace("&nbsp;", " ")
        line = line.replace("&lt;", "<")
        line = line.replace("&gt;", ">")
        line = line.replace("&amp;", "&")
        line = line.replace("&quot;", '"')

        if line.strip():
            md_lines.append(line.strip())

    result = "\n".join(md_lines)

    if len(result) > max_chars:
        result = result[:max_chars] + f"\n... (truncated, total {len(result)} chars)"

    _log.info("WebFetch: done, url=%s, result_chars=%d", url, len(result))
    return result
