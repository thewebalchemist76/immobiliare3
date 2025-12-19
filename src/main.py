import asyncio
from apify import Actor
from src.scraper import ImmobiliareScraper


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        Actor.log.info(f"INPUT RICEVUTO: {actor_input}")

        filters = {
            # autocomplete LIVE
            "location_query": actor_input.get("location_query", "").strip(),
            "location_id": actor_input.get("location_id"),

            # operation
            "operation": actor_input.get("operation", "vendita"),

            # price
            "min_price": actor_input.get("min_price"),
            "max_price": actor_input.get("max_price"),

            # size
            "min_size": actor_input.get("min_size"),
            "max_size": actor_input.get("max_size"),

            # rooms
            "min_rooms": actor_input.get("min_rooms"),
            "max_rooms": actor_input.get("max_rooms"),

            # features
            "garden": actor_input.get("garden", "Indifferente"),
            "terrace": actor_input.get("terrace", False),
            "balcony": actor_input.get("balcony", False),
            "lift": actor_input.get("lift", False),
            "furnished": actor_input.get("furnished", False),
            "pool": actor_input.get("pool", False),
            "exclude_auctions": actor_input.get("exclude_auctions", False),
        }

        max_pages = int(actor_input.get("max_items", 1) or 1)

        scraper = ImmobiliareScraper(filters)
        await scraper.run(max_pages=max_pages)


if __name__ == "__main__":
    asyncio.run(main())
