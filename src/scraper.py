# src/scraper.py
import asyncio
import random
from typing import Dict, List
from urllib.parse import urlparse

from apify import Actor
from playwright.async_api import async_playwright, Page
from nopecha import NoPecha  # NopeCHA solver

from src.config import REAL_USER_AGENT, VIEWPORT


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"
    NOPECHA_TOKEN = "CSK_8a56a9f74c1678c02a7977ef7f2634e65edf4fde559a7894037f3ab0e3ad6237"  # Il tuo token GRATIS!

    def __init__(self, filters: Dict):
        self.filters = filters
        self.max_retries = 3
        self.solver = NoPecha(self.NOPECHA_TOKEN)

    # -------------------------------------------------
    # Utils
    # -------------------------------------------------
    async def human_pause(self, min_s: int = 4, max_s: int = 8):
        await asyncio.sleep(min_s + random.random() * (max_s - min_s))

    def build_search_url(self) -> str:
        municipality = self.filters.get("municipality", "roma").lower()
        operation = self.filters.get("operation", "vendita").lower()
        return f"{self.BASE_URL}/{operation}-case/{municipality}/"

    async def is_captcha(self, page: Page) -> bool:
        try:
            html = (await page.content()).lower()
            return any(
                x in html for x in ["captcha", "cloudflare", "verify you are human", "recaptcha"]
            )
        except Exception:
            return False

    async def solve_recaptcha(self, page: Page) -> bool:
        """Risolvi reCAPTCHA/hCaptcha con NopeCHA (200 credits gratis)"""
        try:
            Actor.log.info("🔄 Risoluzione CAPTCHA con NopeCHA...")
            result = await self.solver.solve_recaptcha(page)
            if result:
                Actor.log.info("✅ CAPTCHA risolto con NopeCHA!")
                await asyncio.sleep(3)
                return True
            else:
                Actor.log.warning("❌ NopeCHA non ha risolto")
                return False
        except Exception as e:
            Actor.log.error(f"❌ Errore NopeCHA: {e}")
            return False

    # -------------------------------------------------
    # Browser + Proxy (Apify corretto)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Warm-up umano
    # -------------------------------------------------
    async def warmup_flow(self, page: Page):
        await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        await self.human_pause(6, 10)

        await page.mouse.move(300, 400)
        await page.mouse.wheel(0, 1000)
        await self.human_pause(4, 6)

    # -------------------------------------------------
    # Listing links
    # -------------------------------------------------
    async def extract_listing_links(self, page: Page) -> List[str]:
        try:
            await page.wait_for_selector("a[href*='/annunci/']", timeout=8000)
            links = await page.evaluate(
                """
                () => Array.from(
                    document.querySelectorAll("a[href*='/annunci/']")
                ).map(a => a.href)
                """
            )
            return list(set([link for link in links if "annunci" in link]))
        except Exception as e:
            Actor.log.warning(f"Errore estrazione link: {e}")
            return []

    # -------------------------------------------------
    # Runner principale con NopeCHA
    # -------------------------------------------------
    async def run(self, max_pages: int = 1):
        search_url = self.build_search_url()
        Actor.log.info(f"🔍 Search URL: {search_url}")

        for attempt in range(1, self.max_retries + 1):
            Actor.log.info(f"🔁 Tentativo {attempt}/{self.max_retries}")

            playwright = browser = context = page = None

            try:
                playwright, browser, context, page = await self.launch_browser()

                # Warm-up
                await self.warmup_flow(page)

                # Vai alla search
                await page.goto(search_url, wait_until="networkidle", timeout=45000)
                await self.human_pause(8, 12)

                # 🔄 NopeCHA: risolvi CAPTCHA se presente
                if await self.is_captcha(page):
                    Actor.log.warning("⚠️ CAPTCHA rilevato!")
                    solved = await self.solve_recaptcha(page)
                    if not solved:
                        Actor.log.warning("❌ NopeCHA fallito, retry...")
                        continue
                    await self.human_pause(5, 8)

                # Scraping pagine
                page_num = 1
                while page_num <= max_pages:
                    Actor.log.info(f"📄 Pagina {page_num}/{max_pages}")

                    # Scroll umano
                    await page.mouse.wheel(0, 1400)
                    await self.human_pause(5, 8)

                    # Estrai link
                    links = await self.extract_listing_links(page)
                    Actor.log.info(f"🔗 Trovati {len(links)} annunci")

                    # Salva primi 3 (anti-ban)
                    for i, url in enumerate(links[:3]):
                        data = {
                            "url": url,
                            "page": page_num,
                            "position": i + 1,
                            "municipality": self.filters.get("municipality", "roma"),
                        }
                        await Actor.push_data(data)
                        Actor.log.info(f"💾 Salvato: {url}")

                    # Prossima pagina
                    next_btn = await page.query_selector("a.pagination__next:not(.disabled)")
                    if not next_btn:
                        Actor.log.info("✅ Fine pagine")
                        break

                    await next_btn.click()
                    await self.human_pause(7, 11)
                    page_num += 1

                Actor.log.info("✅ Scraping COMPLETATO!")
                break  # Successo, esci dal retry loop

            except Exception as e:
                Actor.log.warning(f"⚠️ Errore tentativo {attempt}: {e}")
                if attempt == self.max_retries:
                    Actor.log.error("❌ Massimi retry raggiunti")

            finally:
                try:
                    if page:
                        await page.close()
                    if context:
                        await context.close()
                    if browser:
                        await browser.close()
                    if playwright:
                        await playwright.stop()
                except Exception:
                    pass

        Actor.log.info("👋 Actor terminato completamente")
