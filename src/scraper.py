import asyncio
import random
from urllib.parse import urlencode
from typing import Dict, List

from apify import Actor
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

from src.config import REAL_USER_AGENT, VIEWPORT


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"

    def __init__(self, filters: Dict):
        self.filters = filters

    def build_search_url(self) -> str:
        municipality = self.filters.get("municipality", "roma").lower()
        operation = self.filters.get("operation", "vendita").lower()
        path = f"/{operation}-case/{municipality}/"
        # qui puoi aggiungere querystring con urlencode(params) se vuoi usare tutti i filtri
        return f"{self.BASE_URL}{path}"

    async def human_pause(self, min_s: int = 2, max_s: int = 4) -> None:
        await asyncio.sleep(min_s + random.random() * (max_s - min_s))

    async def extract_listing_links(self, page: Page) -> List[str]:
        selectors = [
            ".in-card",
            ".nd-list__item.in-realEstateResults__item",
            "article[class*='card']",
        ]

        working_selector = None
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                working_selector = selector
                Actor.log.info(f"Using selector: {selector}")
                break
            except Exception:
                continue

        if not working_selector:
            return []

        links = await page.evaluate(
            f"""
        () => Array.from(
            document.querySelectorAll('{working_selector} a[href*="/annunci/"]')
        ).map(a => a.href)
        """
        )

        return list(set(links))

    async def run(self, max_pages: int = 3) -> None:
        search_url = self.build_search_url()
        Actor.log.info(f"🔍 Search URL: {search_url}")

        proxy_conf = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
        proxy_url = await proxy_conf.new_url()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=50,
                proxy={"server": proxy_url},
            )

            context = await browser.new_context(
                user_agent=REAL_USER_AGENT,
                viewport=VIEWPORT,
                locale="it-IT",
                timezone_id="Europe/Rome",
            )

            page = await context.new_page()

            # entra piano nel sito
            await page.goto(self.BASE_URL)
            await self.human_pause(4, 6)

            await page.goto(search_url, wait_until="networkidle")
            await self.human_pause(5, 7)

            page_num = 1
            while page_num <= max_pages:
                Actor.log.info(f"📄 Pagina risultati {page_num}")

                # finta attività utente
                await page.mouse.move(400, 500)
                await page.mouse.wheel(0, 1200)
                await self.human_pause()

                html = await page.content()
                if "captcha" in html.lower():
                    Actor.log.error("❌ CAPTCHA rilevato sulla pagina lista, stop.")
                    break

                links = await self.extract_listing_links(page)
                Actor.log.info(f"🔗 Link trovati: {len(links)}")

                # TODO: qui puoi iterare sui link e aprire i dettagli

                next_btn = await page.query_selector(
                    "a.pagination__next:not(.disabled)"
                )
                if not next_btn:
                    break

                await next_btn.click()
                await self.human_pause(4, 6)
                page_num += 1

            await browser.close()
