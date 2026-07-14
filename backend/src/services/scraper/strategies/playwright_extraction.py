from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import async_playwright

from src.models.news import News
from src.models.source import NewsSource

from .base import ExtractionStrategy


class PlaywrightExtractionStrategy(ExtractionStrategy):

    MAX_RETRIES = 3

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        return asyncio.run(
            self._extract(source, url)
        )

    async def _extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        for _ in range(self.MAX_RETRIES):

            try:
                return await self._extract_once(
                    source,
                    url,
                )

            except Exception:
                continue

        return None

    async def _extract_once(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True,
            )

            page = await browser.new_page()

            await self._speedup(page)

            await page.goto(
                url,
                wait_until="networkidle",
                timeout=30000,
            )

            await self._scroll(page)

            title = await page.title()

            content = await self._extract_content(page)

            publication_date = await self._extract_date(page)

            author = await self._extract_author(page)

            image = await self._extract_image(page)

            await browser.close()

            if not content:
                return None

            return News(
                title=title,
                url=url,
                source=source.id,
                content=content,
                published_at=publication_date,
                author=author,
                image=image,
            )

    async def _extract_content(self, page):

        article = page.locator("article")

        if await article.count():

            paragraphs = await article.locator(
                "p"
            ).all_inner_texts()

        else:

            paragraphs = await page.locator(
                "p"
            ).all_inner_texts()

        return "\n".join(
            p.strip()
            for p in paragraphs
            if p.strip()
        )

    async def _extract_author(self, page):

        selectors = [
            'meta[name="author"]',
            'meta[property="article:author"]',
            '[rel="author"]',
            '.author',
            '.byline',
        ]

        for selector in selectors:

            locator = page.locator(selector)

            if await locator.count():

                if selector.startswith("meta"):
                    return await locator.first.get_attribute(
                        "content"
                    )

                return await locator.first.inner_text()

        return None

    async def _extract_date(self, page):

        selectors = [
            'meta[property="article:published_time"]',
            'meta[name="publication_date"]',
            "time",
        ]

        for selector in selectors:

            locator = page.locator(selector)

            if await locator.count():

                if selector.startswith("meta"):
                    return await locator.first.get_attribute(
                        "content"
                    )

                return await locator.first.get_attribute(
                    "datetime"
                )

        return None

    async def _extract_image(self, page):

        selectors = [
            'meta[property="og:image"]',
            "article img",
        ]

        for selector in selectors:

            locator = page.locator(selector)

            if await locator.count():

                if selector.startswith("meta"):
                    return await locator.first.get_attribute(
                        "content"
                    )

                return await locator.first.get_attribute(
                    "src"
                )

        return None

    async def _scroll(self, page):

        await page.evaluate(
            """
            async () => {
                for (let i=0;i<8;i++){
                    window.scrollBy(0,document.body.scrollHeight);
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