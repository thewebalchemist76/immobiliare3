import uuid
import httpx
from apify import Actor


class ImmobiliareScraper:
    LISTING_URL = "https://android-imm-v4.ws-app.com/b2c/v1/properties"
    GEO_URL = "https://android-imm-v4.ws-app.com/b2c/v1/geography/autocomplete"

    def __init__(self, filters: dict):
        self.filters = filters

    async def resolve_location_id(self, client: httpx.AsyncClient) -> int:
        query = self.filters.get("location_query")
        if not query:
            raise ValueError("location_query obbligatorio")

        r = await client.get(self.GEO_URL, params={"query": query})
        r.raise_for_status()
        data = r.json()

        q = query.strip().lower()
        city = None
        zone = None

        for item in data:
            parents = [str(p.get("id")) for p in item.get("parents", [])]
            if "IT" not in parents:
                continue

            label = item.get("label", "").strip().lower()

            if item.get("type") == 2 and label == q:
                city = item
                break
            if item.get("type") == 3 and label == q:
                zone = item

        chosen = city or zone
        if not chosen:
            raise ValueError(f"Nessuna location valida per '{query}'")

        Actor.log.info(
            f"📍 Location: {chosen['label']} (id={chosen['id']}, type={chosen['type']})"
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

        # ===== ORDINAMENTO PER DATA =====
        # default: più recenti
        order = f.get("order", "recent")

        params["of"] = "d"
        params["od"] = "d" if order == "recent" else "a"

        # ===== PREZZO =====
        if f.get("min_price") is not None:
            params["pm"] = f["min_price"]
        if f.get("max_price") is not None:
            params["px"] = f["max_price"]

        # ===== SUPERFICIE =====
        if f.get("min_size"):
            params["sm"] = f["min_size"]
        if f.get("max_size"):
            params["sx"] = f["max_size"]

        # ===== LOCALI =====
        if f.get("min_rooms"):
            params["rm"] = f["min_rooms"]
        if f.get("max_rooms"):
            params["rx"] = f["max_rooms"]

        # ===== FEATURES =====
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
            location_id = self.filters.get("location_id")
            if not location_id:
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
                        "raw":
