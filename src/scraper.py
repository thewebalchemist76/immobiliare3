# src/scraper.py
import asyncio
import random
from typing import Dict, List
from urllib.parse import urlparse

from apify import Actor
from playwright.async_api import async_playwright, Page
from nopecha import NoPecha  # Corretta per v2.0.1

from src.config import REAL_USER_AGENT, VIEWPORT


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"
    NOPECHA_TOKEN = "CSK_8a56a9f74c1678c02a7977ef7f2634e65edf4fde559a7894037f3ab0e3ad6237"

    def __init__(self, filters: Dict):
        self.filters = filters
        self.max_retries = 3
        self.solver = NoPecha()  # Inizializza senza token (usa quello globale)

    async def human_pause(self, min_s: int = 4, max_s: int = 8):
        await asyncio.sleep(min_s + random.random() * (max_s - min_s))

    def build_search_url(self) -> str:
        municipality = self.filters.get("municipality", "roma").lower()
        operation = self.filters.get("operation", "vendita").lower()
        return f"{self.BASE_URL}/{operation}-case/{municipality}/"

    async def is_captcha(self, page: Page) -> bool:
        try:
            html = (await page.content()).lower()
            return any(x in html for x in ["captcha", "cloudflare", "verify you are human", "recaptcha"])
        except:
            return False

    async def solve_recaptcha(self, page: Page) -> bool:
        """NopeCHA v2.0.1 - API corretta"""
        try:
            Actor.log.info("🔄 NopeCHA solving...")
            # Metodo corretto per v2.0.1
            result = await self.solver.hcaptcha(page.url, page.content())
            if result.get('solution'):
                Actor.log.info("✅ CAPTCHA risolto!")
                await asyncio.sleep(3)
                return True
            Actor.log.warning("❌ NopeCHA failed")
            return False
        except Exception as e:
            Actor.log.error(f"❌ NopeCHA error: {e}")
            return False

    async def launch_browser(self):
        proxy_config = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
        proxy_url = await proxy_config.new_url()
        
        parsed = urlparse(proxy_url)
        proxy_settings = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username,
            "password": parsed.password,
        }

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=100,
            proxy=proxy_settings,
            args=["--disable-blink-features=AutomationControlled"]
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

    async def warmup_flow(self, page: Page):
        await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        await self.human_pause(6, 10)
        await page.mouse.move(300, 400)
        await page.mouse.wheel(0, 1000)
        await self.human_pause(4, 6)

    async def extract_listing_links(self, page: Page) -> List[str]:
        try:
            await page.wait_for_selector("a[href*='/annunci/']", timeout=8000)
            links = await page.evaluate("""
                () => Array.from(
                    document.querySelectorAll("a[href*='/annunci/']")
                ).map(a => a.href)
            """)
            return list(set([link for link in links if "annunci" in link]))
        except:
            return []

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
                    Actor.log.warning("⚠️ CAPTCHA!")
                    if not await self.solve_recaptcha(page):
                        continue

                page_num = 1
                while page_num <= max_pages:
                    Actor.log.info(f"📄 Pagina {page_num}")
                    await page.mouse.wheel(0, 1400)
                    await self.human_pause(5, 8)

                    links = await self.extract_listing_links(page)
                    Actor.log.info(f"🔗 {len(links)} annunci")

                    for url in links[:3]:
                        await Actor.push_data({
                            "url": url,
                            "page": page_num,
                            "municipality": self.filters.get("municipality")
                        })

                    next_btn = await page.query_selector("a.pagination__next:not(.disabled)")
                    if not next_btn:
                        break
                    await next_btn.click()
                    await self.human_pause(7, 11)
                    page_num += 1

                break

            except Exception as e:
                Actor.log.warning(f"⚠️ Errore: {e}")
            finally:
                try:
                    if page: await page.close()
                    if context: await context.close()
                    if browser: await browser.close()
                    if playwright: await playwright.stop()
                except: pass

        Actor.log.info("✅ FINE!")
