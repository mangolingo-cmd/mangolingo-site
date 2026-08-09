"""Fix titles that have an empty cover_url but a known mangadex_id.

Queries the MangaDex cover API in batches of 100 and updates titles.
Safe to re-run.
"""
import asyncio
import os
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def main():
    missing = await db.titles.find(
        {
            "mangadex_id": {"$exists": True, "$ne": None, "$ne": ""},
            "$or": [{"cover_url": ""}, {"cover_url": None}, {"cover_url": {"$exists": False}}],
        },
        {"_id": 0, "id": 1, "title": 1, "mangadex_id": 1},
    ).to_list(length=None)
    print(f"Titles missing cover (with mangadex_id): {len(missing)}")
    if not missing:
        return

    async with httpx.AsyncClient(timeout=20) as c:
        for batch_start in range(0, len(missing), 50):
            batch = missing[batch_start : batch_start + 50]
            ids = [t["mangadex_id"] for t in batch]
            params = [("manga[]", i) for i in ids] + [("limit", 100)]
            r = await c.get("https://api.mangadex.org/cover", params=params)
            if r.status_code != 200:
                print(f"  batch {batch_start}: HTTP {r.status_code}")
                continue
            cov_by_mid: dict[str, str] = {}
            for item in r.json().get("data", []):
                fn = item.get("attributes", {}).get("fileName")
                if not fn:
                    continue
                for rel in item.get("relationships", []):
                    if rel.get("type") == "manga":
                        mid = rel["id"]
                        if mid not in cov_by_mid:
                            cov_by_mid[mid] = (
                                f"https://uploads.mangadex.org/covers/{mid}/{fn}.512.jpg"
                            )
                            break
            updated = 0
            for t in batch:
                url = cov_by_mid.get(t["mangadex_id"])
                if url:
                    await db.titles.update_one({"id": t["id"]}, {"$set": {"cover_url": url}})
                    updated += 1
            print(f"  batch {batch_start}: updated {updated}/{len(batch)}")
            await asyncio.sleep(0.5)

    remaining = await db.titles.count_documents(
        {"$or": [{"cover_url": ""}, {"cover_url": None}, {"cover_url": {"$exists": False}}]}
    )
    print(f"\nTitles still without cover: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
