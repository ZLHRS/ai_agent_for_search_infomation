from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.services.text_tools import html_to_text, normalize_ws


@dataclass(slots=True)
class FetchedPage:
    url: str
    title: str
    text: str
    status_code: int | None = None
    content_type: str = ''
    source_kind: str = 'html'


class HttpFetcher:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                )
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_text_page(self, url: str) -> FetchedPage:
        response = await self._client.get(url)
        content_type = response.headers.get('content-type', '')
        title, body = html_to_text(response.text)
        return FetchedPage(
            url=str(response.url),
            title=title,
            text=body,
            status_code=response.status_code,
            content_type=content_type,
            source_kind='html',
        )

    async def get_bytes(self, url: str) -> tuple[bytes, str, str]:
        response = await self._client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get('content-type', ''), str(response.url)

    async def duckduckgo_site_search(self, domain: str, query: str, limit: int = 4) -> list[str]:
        search_q = f'site:{domain} "{query}"'
        url = f'https://html.duckduckgo.com/html/?q={quote_plus(search_q)}'
        response = await self._client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        urls: list[str] = []
        for a in soup.select('a.result__a, a[data-testid="result-title-a"]'):
            href = a.get('href')
            if href and href.startswith('http'):
                urls.append(href)
            if len(urls) >= limit:
                break
        return list(dict.fromkeys(urls))


async def browser_get_text_page(url: str) -> FetchedPage:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f'Playwright not available: {exc}')

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until='domcontentloaded', timeout=settings.browser_timeout_ms)
        await page.wait_for_timeout(1500)
        title = await page.title()
        text = normalize_ws(await page.text_content('body') or '')
        final_url = page.url
        await browser.close()
        return FetchedPage(url=final_url, title=title, text=text, source_kind='browser')


async def gather_limited(coros: Iterable, limit: int) -> list:
    semaphore = asyncio.Semaphore(limit)

    async def runner(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(runner(c) for c in coros), return_exceptions=True)
