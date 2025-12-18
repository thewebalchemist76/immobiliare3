import uuid
import httpx
from apify import Actor


class ImmobiliareScraper:
    LISTING_URL = "https://android-imm-v4.ws-app.com/b2c/v1/properties"
    GEO_URL = "https://android-imm-v4.ws-app.com/b2c/v1/geography/autocomplete"

    def __init__(self, filters: dict):
        self.filters = filters

    async def resolve_location_id(self, client: httpx.AsyncClient) -> int:
        # override manuale
        if self.filters.get("location_id"):
            return int(self.filters["location_id"])

        query = self.filters.get("location_query")
        if not query:
            raise ValueError("Devi fornire una città o zona")

        r = await client.get(self.GEO_URL, params={"query": query})
        r.raise_for_status()
        data = r.json()

        query_l = query.lower()
        city_match = None
        zone_match = None

        for item in data:
            parent_ids = [p["id"] for p in item.get("parents", [])]
            if "IT" not in parent_ids:
                continue

            label_l = item.get("label", "").lower()

            # PRIORITÀ: comune
            if item.get("type") == 2 and label_l == query_l:
                city_match = item
                break

            # fallback: quartiere
            if item.get("type") == 3 and label_l == query_l:
                zone_match = item

        chosen = city_match or zone_match
        if not chosen:
            raise ValueError(f"Nessuna location valida trovata per '{query}'")

        Actor.log.info(
            f"📍 Location risolta: {chosen['label']} (id={chosen['id']}, type={chosen['type']})"
        )
        return int(chosen["id"])

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

        if f.get("min_price") is not None:
            params["pm"] = f["min_price"]
        if f.get("max_price") is not None:
            params["px"] = f["max_price"]

        if f.get("min_size"):
            params["sm"] = f["min_size"]
        if f.get("max_size"):
            params["sx"] = f["max_size"]

        if f.get("min_rooms"):
            params["rm"] = f["min_rooms"]
        if f.get("max_rooms"):
            params["rx"] = f["max_rooms"]

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
            location_id = await self.resolve_location_id(client)

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
