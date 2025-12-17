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
            slow_mo=150,
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
        
        await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=40000)
        await self.human_pause(8, 12)
        
        for _ in range(3):
            await page.mouse.wheel(0, random.randint(800, 1500))
            await self.human_pause(2, 4)
        
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
            ".search-result-card a[href*='/annunci/']",
            "[data-element='card'] a[href*='/annunci/']",
            "article a[href*='/annunci/']"
        ]
        
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                links = await page.evaluate(f"""
                    () => {{
                        const els = document.querySelectorAll('{selector}');
                        return Array.from(els)
                            .map(a => a.href)
                            .filter(href => href && href.includes('/annunci/') && !href.includes('tel:'))
                            .slice(0, 20);  // Max 20 per pagina
                    }}
                """)
                if links:
                    Actor.log.info(f"✅ Selector '{selector}' funziona: {len(links)} link")
                    return list(set(links))
            except Exception as e:
                Actor.log.debug(f"Selector {selector} fallito: {e}")
                continue
        
        Actor.log.warning("❌ Nessun selector ha trovato link")
        return []

    async def run(self, max_pages: int = 1):
        search_url = self.build_search_url()
        Actor.log.info(f"🔍 Search URL: {search_url}")

        for attempt in range(1, self.max_retries + 1):
            Actor.log.info(f"🔁 Tentativo {attempt}/{self.max_retries}")
            playwright = browser = context = page = None
            total_links = 0

            try:
                playwright, browser, context, page = await self.launch_browser()
                await self.warmup_flow(page)

                await page.goto(search_url, wait_until="networkidle", timeout=60000)
                await self.human_pause(10, 15)

                # 🔍 DEBUG CAPTCHA + Screenshot
                if await self.is_captcha(page):
                    Actor.log.warning("⚠️ CAPTCHA rilevato, salvo debug...")
                    
                    # Screenshot
                    screenshot_bytes = await page.screenshot(full_page=True)
                    await Actor.push_data({
                        "debug_type": "captcha_screenshot",
                        "attempt": attempt,
                        "municipality": self.filters.get("municipality")
                    })
                    
                    # HTML snippet
                    html_snippet = (await page.content())[:3000]
                    await Actor.push_data({
                        "debug_type": "captcha_html",
                        "attempt": attempt,
                        "html_preview": html_snippet,
                        "municipality": self.filters.get("municipality")
                    })
                    
                    # Prova scroll per refresh
                    await page.mouse.wheel(0, 2000)
                    await self.human_pause(5, 8)

                page_num = 1
                while page_num <= max_pages:
                    Actor.log.info(f"📄 Pagina {page_num}/{max_pages}")
                    
                    await page.mouse.move(random.randint(200, 800), random.randint(300, 700))
                    await page.mouse.wheel(0, random.randint(1000, 2000))
                    await self.human_pause(6, 10)

                    links = await self.extract_listing_links(page)
                    Actor.log.info(f"🔗 Trovati {len(links)} annunci")

                    for i, url in enumerate(links[:10]):
                        data = {
                            "url": url,
                            "page": page_num,
                            "municipality": self.filters.get("municipality", "Roma"),
                            "operation": self.filters.get("operation", "vendita"),
                            "position": i + 1,
                            "attempt": attempt
                        }
                        await Actor.push_data(data)
                        total_links += 1

                    next_btn = await page.query_selector("a.pagination__next:not(.disabled), .pagination-next:not(.disabled)")
                    if not next_btn:
                        Actor.log.info("✅ Nessuna pagina successiva")
                        break

                    await next_btn.click()
                    await self.human_pause(10, 15)
                    page_num += 1

                Actor.log.info(f"✅ Tentativo {attempt} completato: {total_links} link totali")
                if total_links > 0:
                    break  # Successo!

            except Exception as e:
                Actor.log.warning(f"⚠️ Errore tentativo {attempt}: {str(e)[:100]}")
            finally:
                try:
                    if page: await page.close()
                    if context: await context.close()
                    if browser: await browser.close()
                    if playwright: await playwright.stop()
                except: pass

        Actor.log.info(f"👋 Actor terminato. Link totali: {total_links}")
