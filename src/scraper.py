import uuid
import httpx
from apify import Actor


class ImmobiliareScraper:
    LISTING_URL = "https://android-imm-v4.ws-app.com/b2c/v1/properties"
    GEO_URL = "https://android-imm-v4.ws-app.com/b2c/v1/geography/autocomplete"

    def __init__(self, filters: dict):
        self.filters = filters

    async def resolve_location_id(self, client: httpx.AsyncClient) -> int:
        """
        Risolve automaticamente location_query -> location_id
        usando geography/autocomplete (solo IT, type 2 o 3).
        """
        # override manuale
        if self.filters.get("location_id"):
            return int(self.filters["location_id"])

        query = self.filters.get("location_query")
        if not query:
            raise ValueError("Devi fornire una città o zona")

        r = await client.get(self.GEO_URL, params={"query": query})
        r.raise_for_status()
        data = r.json()

        for item in data:
            parent_ids = [p["id"] for p in item.get("parents", [])]
            if (
                "IT" in parent_ids
                and item.get("type") in (2, 3)
            ):
                Actor.log.info(
                    f"📍 Location risolta: {item['label']} (id={item['id']})"
                )
                return int(item["id"])

        raise ValueError(f"Nessuna location valida trovata per '{query}'")

    def build_params(self, location_id: int, start: int) -> dict:
        f = self.filters
        op = (f.get("operation") or "").lower()

        params = {
            "c": location_id,
            "cat": 1,
            "t": "a" if op == "affitto" else "v",
            "start": start,
            "size": 25,
        }

        # price
        if f.get("min_price") is not None:
            params["pm"] = f["min_price"]
        if f.get("max_price") is not None:
            params["px"] = f["max_price"]

        # size
        if f.get("min_size"):
            params["sm"] = f["min_size"]
        if f.get("max_size"):
            params["sx"] = f["max_size"]

        # rooms
        if f.get("min_rooms"):
            params["rm"] = f["min_rooms"]
        if f.get("max_rooms"):
            params["rx"] = f["max_rooms"]

        # features
        if f.get("lift"):
            params["ac2_ascensore"] = 1
        if f.get("garden") in ("privato", "comune"):
            params["ac3_giard"] = 10
        if f.get("terrace"):
            params["ac1_terr"] = 1
        if f.get("balcony"):
            params["ac1_bal"] = 1
        if f.get("pool"):
            params["ac1_pisc"] = 1
        if f.get("furnished"):
            params["arred"] = 1
        if f.get("exclude_auctions"):
            params["noAste"] = 1

        return params

    async def run(self, max_pages: int = 1):
        headers = {
            "User-Agent": "WSCommand3<Furious>|REL|PRD|ANDROID",
            "Accept-Language": "it-IT",
            "x-currency": "EUR",
            "x-measurement-unit": "meters",
            "immo-id": str(uuid.uuid4()),
        }

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            # 1️⃣ resolve city / zone
            location_id = await self.resolve_location_id(client)

            # 2️⃣ listings
            for page in range(max_pages):
                start = page * 25
                params = self.build_params(location_id, start)

                Actor.log.info(f"📄 Page {page + 1} params={params}")

                r = await client.get(self.LISTING_URL, params=params)
                r.raise_for_status()

                data = r.json()
                items = data.get("list", [])

                if not items:
                    Actor.log.info("⛔ Nessun altro risultato")
                    break

                for item in items:
                    geo = item.get("geography", {})
                    await Actor.push_data({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "price": item.get("price"),
                        "city": geo.get("municipality", {}).get("name"),
                        "province": geo.get("province", {}).get("name"),
                        "url": f"https://www.immobiliare.it/annunci/{item.get('id')}/",
                        "raw": item,
                    })
