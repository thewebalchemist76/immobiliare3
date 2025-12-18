import asyncio
from apify import Actor
from src.scraper import ImmobiliareScraper


def b(value):
    """Normalizza boolean -> True/False o None"""
    if value is None:
        return None
    return bool(value)


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}

        filters = {
            # base
            "municipality": actor_input.get("municipality", "roma"),
            "operation": actor_input.get("operation", "vendita"),

            # range numerici
            "min_price": actor_input.get("min_price"),
            "max_price": actor_input.get("max_price"),
            "min_size": actor_input.get("min_size"),
            "max_size": actor_input.get("max_size"),
            "min_rooms": actor_input.get("min_rooms"),
            "max_rooms": actor_input.get("max_rooms"),
            "bathrooms": actor_input.get("bathrooms"),

            # select
            "property_condition": actor_input.get("property_condition"),
            "floor": actor_input.get("floor"),
            "garage": actor_input.get("garage"),
            "heating": actor_input.get("heating"),
            "garden": actor_input.get("garden"),

            # boolean (→ ac* params lato scraper)
            "terrace": b(actor_input.get("terrace")),
            "balcony": b(actor_input.get("balcony")),
            "lift": b(actor_input.get("lift")),
            "furnished": b(actor_input.get("furnished")),
            "cellar": b(actor_input.get("cellar")),
            "pool": b(actor_input.get("pool")),
            "exclude_auctions": b(actor_input.get("exclude_auctions")),
            "virtual_tour": b(actor_input.get("virtual_tour")),

            # testo
            "keywords": actor_input.get("keywords"),
        }

        max_pages = actor_input.get("max_items", 3)

        scraper = ImmobiliareScraper(filters)
        await scraper.run(max_pages=max_pages)


if __name__ == "__main__":
    asyncio.run(main())