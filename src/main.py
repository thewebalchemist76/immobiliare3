import asyncio
from apify import Actor
from src.scraper import ImmobiliareScraper


def normalize_location(actor_input: dict) -> str | None:
    # 1️⃣ location_query esplicita
    loc = actor_input.get("location_query")
    if isinstance(loc, str) and loc.strip():
        return loc.strip()

    # 2️⃣ municipality top-level
    mun = actor_input.get("municipality")
    if isinstance(mun, str) and mun.strip():
        return mun.strip()

    # 3️⃣ municipality annidata (caso Apify)
    nested = actor_input.get("input", {}).get("municipality")
    if isinstance(nested, str) and nested.strip():
        return nested.strip()

    return None


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}

        location_query = normalize_location(actor_input)

        filters = {
            "location_query": location_query,
            "operation": actor_input.get("operation", "vendita"),
            "min_price": actor_input.get("min_price"),
            "max_price": actor_input.get("max_price"),
            "min_size": actor_input.get("min_size"),
            "max_size": actor_input.get("max_size"),
            "min_rooms": actor_input.get("min_rooms"),
            "max_rooms": actor_input.get("max_rooms"),
            "bathrooms": actor_input.get("bathrooms"),
            "property_condition": actor_input.get("property_condition"),
            "floor": actor_input.get("floor"),
            "garage": actor_input.get("garage"),
            "heating": actor_input.get("heating"),
            "garden": actor_input.get("garden"),
            "terrace": actor_input.get("terrace"),
            "balcony": actor_input.get("balcony"),
            "lift": actor_input.get("lift"),
            "furnished": actor_input.get("furnished"),
            "cellar": actor_input.get("cellar"),
            "pool": actor_input.get("pool"),
            "exclude_auctions": actor_input.get("exclude_auctions"),
            "virtual_tour": actor_input.get("virtual_tour"),
            "keywords": actor_input.get("keywords"),
        }

        max_pages = actor_input.get("max_items", 1)

        Actor.log.info(f"INPUT NORMALIZZATO: {filters}")

        scraper = ImmobiliareScraper(filters)
        await scraper.run(max_pages=max_pages)


if __name__ == "__main__":
    asyncio.run(main())
