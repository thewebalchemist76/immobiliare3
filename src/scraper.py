# scraper.py
import asyncio
import random
from typing import Dict, List

from apify import Actor
from playwright.async_api import async_playwright, Page

from src.config import REAL_USER_AGENT, VIEWPORT


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"

    def __init__(self, filters: Dict):
        self.filters = filters
        self.max_retries = 2

    # ----------------------------
    # Utils
    # ----------------------------
    async def human_pause(self, min_s: int = 4, max_s: int = 8):
        await asyncio.sleep(min_s + random.random() * (max_s - min_s))

    def build_search_url(self) -> str:
        municipality = self.filters.get("municipality", "roma").lower()
        operation = self.filters.get("operation", "vendita").lower()
        return f"{self.BASE_URL}/{operation}-case/{municipality}/"

    async def is_captcha(self, page: Page) -> bool:
        try:
            content = (await page.content()).lower()
            return any(k in content for k in ["captcha", "cloudflare", "verify you are human"])
        except Exception:
            return False

    # ----------------------------
    # Browser / Proxy (CORRETTO PER APIFY PYTHON)
    # ----------------------------
    async def launch_browser(self):
        # Metodo CORRETTO per apify>=3.x
        proxy_config = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
        proxy_url = proxy_config.new_url()

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=100,
            proxy={"server": proxy_url},
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            user_agent=REAL_USER_AGENT,
            viewport=VIEWPORT,
            locale="it-IT",
            timezone_id="Europe/Rome",
            ignore_https_errors=True,
        )

        page = await context.new_page()
        return playwright, browser, context, page

    # ----------------------------
    # Anti-captcha warmup
    # ----------------------------
    async def warmup_flow(self, page: Page):
        try:
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            raise RuntimeError("Proxy / network error on homepage")

        await self.human_pause(6, 10)

        await page.mouse.move(250, 350)
        await page.mouse.wheel(0, 1000)
        await self.human_pause(4, 6)

        try:
            buy_btn = await page.query_selector("a:has-text('Compra')")
            if buy_btn:
                await buy_btn.click()
                await self.human_pause(6, 9)
        except Exception:
            pass

    # ----------------------------
    # Listing extraction
    # ----------------------------
    async def extract_listing_links(self, page: Page) -> List[str]:
        try:
            await page.wait_for_selector("a[href*='/annunci/']", timeout=8000)
            links = await page.evaluate(
                """
                () => Array.from(document.querySelectorAll("a[href*='/annunci/']")).map(a => a.href)
                """
            )
            return list(set(links))
        except Exception:
            return []

    # ----------------------------
    # Main runner with retry
    # ----------------------------
    async def run(self, max_pages: int = 1):
        search_url = self.build_search_url()
        Actor.log.info(f"🔍 Search URL: {search_url}")

        for attempt in range(1, self.max_retries + 1):
            Actor.log.info(f"🔁 Tentativo {attempt}/{self.max_retries}")
            playwright = browser = context = page = None

            try:
                playwright, browser, context, page = await self.launch_browser()

                await self.warmup_flow(page)

                await page.goto(search_url, wait_until="networkidle", timeout=45000)
                await self.human_pause(8, 12)

                if await self.is_captcha(page):
                    raise RuntimeError("CAPTCHA on listing")

                page_num = 1
                while page_num <= max_pages:
                    Actor.log.info(f"📄 Pagina risultati {page_num}")
                    await page.mouse.wheel(0, 1400)
                    await self.human_pause(5, 8)

                    links = await self.extract_listing_links(page)
                    Actor.log.info(f"🔗 Annunci trovati: {len(links)}")

                    for url in links[:5]:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await self.human_pause(7, 11)

                        if await self.is_captcha(page):
                            Actor.log.warning("⚠️ CAPTCHA in annuncio, skip")
                            continue

                        Actor.push_data({"url": url})

                    next_btn = await page.query_selector("a.pagination__next:not(.disabled)")
                    if not next_btn:
                        break

                    await next_btn.click()
                    await self.human_pause(7, 11)
                    page_num += 1

                Actor.log.info("✅ Scraping completato")
                break

            except RuntimeError as e:
                Actor.log.warning(f"⚠️ {e} → retry")

            finally:
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

        Actor.log.info("🏁 Actor terminato")
