"""
Playwright scraping strategies.
"""
from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from src.models.source import NewsSource

from .base import DiscoveryStrategy


class PlaywrightDiscoveryStrategy(DiscoveryStrategy):

    ARTICLE_PATTERNS = (
        "/news/",
        "/article/",
        "/story/",
        "/202",
    )

    EXCLUDED = (
        "/tag/",
        "/author/",
        "/category/",
        "/topics/",
        "/search",
        "/privacy",
        "/cookie",
        "/contact",
        "/about",
        "/login",
        "/subscribe",
        "#",
    )

    def discover(self, source: NewsSource) -> list[str]:
        return asyncio.run(self._discover(source))

    async def _discover(self, source: NewsSource) -> list[str]:

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            await self._speedup(page)

            await page.goto(
                str(source.base_url),
                wait_until="networkidle",
            )

            await self._scroll(page)

            urls = await page.locator(
                "a[href]"
            ).evaluate_all(
                "els => els.map(e => e.href)"
            )

            await browser.close()

        discovered = []

        for url in urls:

            if not url.startswith(str(source.base_url)):
                continue

            if any(x in url.lower() for x in self.EXCLUDED):
                continue

            if any(x in url.lower() for x in self.ARTICLE_PATTERNS):
                discovered.append(url)

        return list(dict.fromkeys(discovered))

    async def _scroll(self, page):

        await page.evaluate(
            """
            async () => {
                for (let i=0;i<8;i++){
                    window.scrollBy(0, document.body.scrollHeight);
                    await new Promise(r=>setTimeout(r,300));
                }
            }
            """
        )

    async def _speedup(self, page):

        await page.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type
                in {"image", "font", "media"}
                else route.continue_()
            ),
        )


