import math
import httpx
from apify import Actor


class ImmobiliareScraper:
    BASE_URL = "https://android-imm-v4.ws-app.com/b2c/v1/properties"

    def __init__(self, filters: dict):
        self.filters = filters

    def build_params(self, start: int = 0) -> dict:
        f = self.filters

        params = {
            "c": self.city_to_id(f.get("municipality")),
            "cat": 1,  # case
            "t": "v" if f.get("operation") == "vendita" else "a",
            "start": start,
        }

        # range
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

        # boolean → API flags
        if f.get("lift"):
            params["ac2_ascensore"] = 1
        if f.get("garden"):
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

    async def run(self, max_pages: int = 3):
        headers = {
            "user-agent": "WSCommand3<Furious>|REL|PRD|ANDROID",
            "accept-language": "it-IT",
            "x-currency": "EUR",
            "x-measurement-unit": "meters",
        }

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            for page in range(max_pages):
                start = page * 25
                params = self.build_params(start=start)

                Actor.log.info(f"📄 Page {page+1} params={params}")

                r = await client.get(self.BASE_URL, params=params)
                r.raise_for_status()

                data = r.json()
                items = data.get("items", [])

                if not items:
                    Actor.log.info("⛔ Nessun altro risultato")
                    break

                for item in items:
                    await Actor.push_data({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "price": item.get("price"),
                        "city": item.get("city"),
                        "url": f"https://www.immobiliare.it/annunci/{item.get('id')}/",
                        "raw": item,
                    })

    def city_to_id(self, name: str) -> int:
        """MVP: hardcoded – poi DB o API"""
        mapping = {
            "roma": 6737,
            "chieti": 4617,
        }
        return mapping.get(name.lower(), 6737)
