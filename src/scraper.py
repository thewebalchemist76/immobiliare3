# src/scraper.py
import asyncio
import random
from typing import Dict, List
from urllib.parse import urlparse

from apify import Actor
from playwright.async_api import async_playwright, Page

from src.config import REAL_USER_AGENT, VIEWPORT


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"

    def __init__(self, filters: Dict):
        self.filters = filters
        self.max_retries = 3

    async def human_pause(self, min_s: int = 4, max_s: int = 8):
        await asyncio.sleep(min_s + random.random() * (max_s - min_s))

    def build_search_url(self) -> str:
        municipality = self.filters.get("municipality", "roma").lower()
        operation = self.filters.get("operation", "vendita").lower()
        return f"{self.BASE_URL}/{operation}-case/{municipality}/"

    async def is_captcha(self, page: Page) -> bool:
        try:
            html = (await page.content()).lower()
            captcha_keywords = ["captcha", "cloudflare", "verify you are human", "recaptcha", "human verification"]
            return any(keyword in html for keyword in captcha_keywords)
        except:
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
            slow_mo=150,  # Più lento = più umano
            proxy=proxy_settings,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ]
        )

        context = await browser.new_context(
            user_agent=REAL_USER_AGENT,
            viewport=VIEWPORT,
            locale="it-IT",
            timezone_id="Europe/Rome",
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
            }
        )
        page = await context.new_page()
        return playwright, browser, context, page

    async def warmup_flow(self, page: Page):
        """Simula comportamento umano estremo"""
        Actor.log.info("🔥 Warm-up umano avanzato...")
        
        # Homepage lenta
        await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=40000)
        await self.human_pause(8, 12)
        
        # Scroll multiplo casuale
        for _ in range(3):
            await page.mouse.wheel(0, random.randint(800, 1500))
            await self.human_pause(2, 4)
        
        # Cerca barra di ricerca
        try:
            search_input = await page.query_selector("input[placeholder*='cerca']")
            if search_input:
                await search_input.click()
                await self.human_pause(2, 3)
        except:
            pass

    async def extract_listing_links(self, page: Page) -> List[str]:
        selectors = [
            "a[href*='/annunci/']",
            ".in-card a[href*='/annunci/']",
            ".search-result-card a[href*='/annunci/']"
        ]
        
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                links = await page.evaluate(f"""
                    () => Array.from(
                        document.querySelectorAll('{selector}')
                    ).map(a => a.href).filter(href => href.includes('/annunci/'))
                """)
                if links:
                    return list(set(links))
            except:
                continue
        return []

    async def run(self, max_pages: int = 1):
        search_url = self.build_search_url()
        Actor.log.info(f"🔍 Search: {search_url}")

        for attempt in range(1, self.max_retries + 1):
            Actor.log.info(f"🔁 Tentativo {attempt}/3")
            playwright = browser = context = page = None

            try:
                playwright, browser, context, page = await self.launch_browser()
                await self.warmup_flow(page)

                # Navigazione diretta alla search
                await page.goto(search_url, wait_until="networkidle", timeout=60000)
                await self.human_pause(10, 15)

                # CAPTCHA check ma NON bloccante
                if await self.is_captcha(page):
                    Actor.log.warning("⚠️ CAPTCHA rilevato, continuo comunque...")
                    # Prova scroll per refresh dinamico
                    await page.mouse.wheel(0, 2000)
                    await self.human_pause(5, 8)

                page_num = 1
                total_links = 0
                
                while page_num <= max_pages:
                    Actor.log.info(f"📄 Pagina {page_num}/{max_pages}")
                    
                    # Scroll umano
                    await page.mouse.move(random.randint(200, 800), random.randint(300, 700))
                    await page.mouse.wheel(0, random.randint(1000, 2000))
                    await self.human_pause(6, 10)

                    # Estrai link
                    links = await self.extract_listing_links(page)
                    Actor.log.info(f"🔗 {len(links)} annunci trovati")

                    # Salva TUTTI i link (non solo primi 3)
                    for i, url in enumerate(links[:10]):  # Max 10 per pagina
                        data = {
                            "url": url,
                            "page": page_num,
                            "municipality": self.filters.get("municipality", "Roma"),
                            "operation": self.filters.get("operation", "vendita"),
                            "position": i + 1
                        }
                        await Actor.push_data(data)
                        total_links += 1

                    # Prossima pagina
                    next_btn = await page.query_selector("a.pagination__next:not(.disabled), .pagination-next:not(.disabled)")
                    if not next_btn:
                        Actor.log.info("✅ Fine pagine")
                        break

                    await next_btn.click()
                    await self.human_pause(10, 15)
                    page_num += 1

                Actor.log.info(f"✅ COMPLETATO! {total_links} link totali salvati")
                break

            except Exception as e:
                Actor.log.warning(f"⚠️ Errore: {str(e)[:100]}...")
            finally:
                try:
                    if page: await page.close()
                    if context: await context.close()
                    if browser: await browser.close()
                    if playwright: await playwright.stop()
                except: pass

        Actor.log.info("👋 Actor terminato")

