import asyncio
import random
from urllib.parse import urlencode
from apify import Actor
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


from src.config import REAL_USER_AGENT, VIEWPORT




class ImmobiliareScraper:
BASE_URL = "https://www.immobiliare.it"


def __init__(self, filters: dict):
self.filters = filters


def build_search_url(self) -> str:
municipality = self.filters.get("municipality", "roma").lower()
operation = self.filters.get("operation", "vendita").lower()
path = f"/{operation}-case/{municipality}/"
return f"{self.BASE_URL}{path}"


async def human_pause(self, min_s=2, max_s=4):
await asyncio.sleep(min_s + random.random() * (max_s - min_s))


async def run(self, max_pages: int = 3):
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


# 🔹 entra piano nel sito
await page.goto(self.BASE_URL)
await self.human_pause(4, 6)


await page.goto(search_url, wait_until="networkidle")
await self.human_pause(5, 7)


page_num = 1
while page_num <= max_pages:
Actor.log.info(f"📄 Pagina risultati {page_num}")


await page.mouse.move(400, 500)
await page.mouse.wheel(0, 1200)
await self.human_pause()


links = await page.evaluate("""
await page.close()