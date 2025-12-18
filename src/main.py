import asyncio
from apify import Actor
from src.scraper import ImmobiliareScraper


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}

        filters = {
            "city_id": actor_input.get("city_id"),
            "municipality": actor_input.get("municipality", ""),
            "operation": actor_input.get("operation", "vendita"),
            "min_price": actor_input.get("min_price"),
            "max_price": actor_input.get("max_price"),
            "min_size": actor_input.get("min_size"),
            "max_size": actor_input.get("max_size"),
            "min_rooms": actor_input.get("min_rooms"),
            "max_rooms": actor_input.get("max_rooms"),
            "bathrooms": actor_input.get("bathrooms"),
            "garden": actor_input.get("garden", "Indifferente"),
            "terrace": actor_input.get("terrace", False),
            "balcony": actor_input.get("balcony", False),
            "lift": actor_input.get("lift", False),
            "furnished": actor_input.get("furnished", False),
            "cellar": actor_input.get("cellar", False),
            "pool": actor_input.get("pool", False),
            "exclude_auctions": actor_input.get("exclude_auctions", False),
            "virtual_tour": actor_input.get("virtual_tour", False),
            "keywords": actor_input.get("keywords", ""),
        }

        max_pages = int(actor_input.get("max_items", 1) or 1)

        scraper = ImmobiliareScraper(filters)
        await scraper.run(max_pages=max_pages)


if __name__ == "__main__":
    asyncio.run(main())
