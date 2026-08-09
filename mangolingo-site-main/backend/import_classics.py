"""Import classic/old popular manhwa by direct name search."""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
import httpx

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

# Old/classic + popular manhwa to ensure are in catalog
CLASSIC_TITLES = [
    "Magic Emperor", "Martial Peak", "Tales of Demons and Gods",
    "Apotheosis", "Soul Land", "Versatile Mage",
    "The Strongest System", "I'm Really Not the Demon God's Lackey",
    "King of Hell", "Hyer Edge", "Lookism", "The Boxer",
    "Painter of the Night", "Webtoon Character Na Kang Lim",
    "Eleceed", "Noblesse", "Cheating Men Must Die",
    "Ghost Wife", "Daddy Will Run Away", "Reborn to Master the Blade",
    "The Newbie is Too Strong", "Solo Spell Caster",
    "Limitless Crafting", "Reawakened Player", "Necromancer Survival",
    "Worthless Regression", "Player Reborn", "Sword Sheath's Child",
    "The Tutorial Tower of the Advanced Player", "Tomb Raider King",
    "Reverse Villain", "The S-Classes That I Raised",
    "Rebirth of the Urban Immortal Cultivator", "Demon Lord, Retry!",
    "Tenkaichi - Nihon Saikyou Mononofu Ketteisen",
    "The Beginning After the End", "Solo Leveling",
    "Hardcore Leveling Warrior", "Second Life Ranker",
    "Tower of God", "The God of High School",
    "Bastard", "Sweet Home", "Pigpen",
    "Wind Breaker", "Yumi's Cells",
    "Manhole", "Manager Kim", "The Live",
    "Trinity Wonder", "Free Throw", "Hellbound",
    "True Beauty", "Get Schooled", "Lookism",
    "Annarasumanara", "Cheese in the Trap",
    "Refund High School", "Hooky", "Tower of God: Season 1",
    "Maru is a Puppy", "Bloody Sweet", "Suicide Boy",
    "Doctor Elise", "The Beginning of the End",
    "Reborn Rich Heiress", "I'm the Queen in This Life",
    "I Picked Up a Self-Proclaimed Crown Prince",
    "Death Is The Only Ending For The Villainess",
    "The Villainess Reverses the Hourglass",
]

MD_BASE = "https://api.mangadex.org"
MD_UP = "https://uploads.mangadex.org"

async def main():
    added = 0
    skipped = 0
    not_found = 0
    async with httpx.AsyncClient(timeout=30) as h:
        for name in CLASSIC_TITLES:
            try:
                r = await h.get(
                    f"{MD_BASE}/manga",
                    params=[
                        ("title", name), ("limit", "3"),
                        ("availableTranslatedLanguage[]", "en"),
                        ("includes[]", "cover_art"),
                        ("contentRating[]", "safe"),
                        ("contentRating[]", "suggestive"),
                    ],
                )
                results = r.json().get("data") or []
                if not results:
                    not_found += 1
                    continue
                item = results[0]
                md_id = item["id"]
                if await db.titles.find_one({"mangadex_id": md_id}):
                    skipped += 1
                    continue
                attrs = item.get("attributes") or {}
                ttype = "manhwa" if attrs.get("originalLanguage") == "ko" else "manga"
                tt = attrs.get("title") or {}
                title_en = tt.get("en") or next(iter(tt.values()), name)
                title_ar = next((a["ar"] for a in (attrs.get("altTitles") or []) if "ar" in a), "")
                cover_fn = ""
                for rel in item.get("relationships") or []:
                    if rel.get("type") == "cover_art":
                        cover_fn = (rel.get("attributes") or {}).get("fileName") or ""
                        break
                cover_url = f"{MD_UP}/covers/{md_id}/{cover_fn}.512.jpg" if cover_fn else ""
                doc = {
                    "id": str(uuid.uuid4()),
                    "mangadex_id": md_id,
                    "type": ttype,
                    "title": title_en,
                    "title_ar": title_ar,
                    "synopsis": (attrs.get("description") or {}).get("en", "")[:1200],
                    "cover_url": cover_url,
                    "banner_url": cover_url,
                    "genres": [(((t.get("attributes") or {}).get("name") or {}).get("en") or "") for t in (attrs.get("tags") or [])][:8],
                    "status": "ongoing",
                    "episodes": None,
                    "chapters": None,
                    "year": attrs.get("year"),
                    "rating_avg": 0, "rating_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                doc["genres"] = [g for g in doc["genres"] if g]
                await db.titles.insert_one(doc)
                added += 1
            except Exception:
                not_found += 1
    print(f"Added: {added}, Skipped (already exists): {skipped}, Not found: {not_found}")

asyncio.run(main())
