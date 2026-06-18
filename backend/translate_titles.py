"""One-shot script to translate English manhwa/manga titles to Arabic using Claude.
Also imports specific popular manhwa by name search.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient
import httpx
from emergentintegrations.llm.chat import LlmChat, UserMessage

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

# Popular manhwa/manga to ensure are in the catalog
POPULAR_TITLES = [
    "Solo Leveling", "Tower of God", "The Beginning After the End",
    "Omniscient Reader's Viewpoint", "Eleceed", "Lookism", "Noblesse",
    "True Beauty", "Sweet Home", "The God of High School",
    "Tomb Raider King", "Hardcore Leveling Warrior",
    "Return of the Mount Hua Sect", "The Player That Can't Level Up",
    "SSS-Class Suicide Hunter", "I'm the Max Level Newbie",
    "Nano Machine", "The Boxer", "Bastard", "Pigpen",
    "Solo Max-Level Newbie", "Reincarnation of the Suicidal Battle God",
    "Pick Me Up, Infinite Gacha", "Worn and Torn Newbie",
    "The Heavenly Demon Can't Live a Normal Life",
    "Doctor's Rebirth", "The Greatest Estate Designer",
    "Skeleton Soldier Couldn't Protect the Dungeon",
    "Damn Reincarnation", "Survival Story of a Sword King in a Fantasy World",
    "Reaper of the Drifting Moon", "Murim Login",
    "Second Life Ranker", "Talent-Swallowing Magician",
    "Manager Kim", "The Live", "Trinity Wonder",
    "Wind Breaker", "Bloody Sweet", "Wind Breaker (Manhwa)",
    "Free Throw", "Yumi's Cells", "Hellbound",
]

MANGADEX_BASE = "https://api.mangadex.org"
MANGADEX_UPLOADS = "https://uploads.mangadex.org"


def _md_extract_cover(rels):
    for r in rels:
        if r.get("type") == "cover_art":
            return (r.get("attributes") or {}).get("fileName") or ""
    return ""


def _md_genres(tags):
    out = []
    for t in tags:
        n = ((t.get("attributes") or {}).get("name") or {}).get("en")
        if n:
            out.append(n)
    return out[:8]


async def import_popular():
    """Search MangaDex by title for each popular series and add if missing."""
    added = 0
    async with httpx.AsyncClient(timeout=30) as h:
        for name in POPULAR_TITLES:
            try:
                r = await h.get(
                    f"{MANGADEX_BASE}/manga",
                    params=[
                        ("title", name),
                        ("limit", "5"),
                        ("availableTranslatedLanguage[]", "en"),
                        ("includes[]", "cover_art"),
                        ("contentRating[]", "safe"),
                        ("contentRating[]", "suggestive"),
                    ],
                )
                r.raise_for_status()
                results = r.json().get("data") or []
                if not results:
                    print(f"  ✗ Not found: {name}")
                    continue
                item = results[0]
                md_id = item["id"]
                if await db.titles.find_one({"mangadex_id": md_id}):
                    print(f"  - Already exists: {name}")
                    continue
                attrs = item.get("attributes") or {}
                ttype = "manhwa" if attrs.get("originalLanguage") == "ko" else "manga"
                titles_d = attrs.get("title") or {}
                title_en = titles_d.get("en") or next(iter(titles_d.values()), "")
                title_ar = next((at["ar"] for at in (attrs.get("altTitles") or []) if "ar" in at), "")
                cover = _md_extract_cover(item.get("relationships") or [])
                cover_url = f"{MANGADEX_UPLOADS}/covers/{md_id}/{cover}.512.jpg" if cover else ""
                doc = {
                    "id": str(uuid.uuid4()),
                    "mangadex_id": md_id,
                    "type": ttype,
                    "title": title_en or name,
                    "title_ar": title_ar,
                    "synopsis": (attrs.get("description") or {}).get("en", "")[:1200],
                    "cover_url": cover_url,
                    "banner_url": cover_url,
                    "genres": _md_genres(attrs.get("tags") or []),
                    "status": "ongoing",
                    "episodes": None,
                    "chapters": None,
                    "year": attrs.get("year"),
                    "rating_avg": 0,
                    "rating_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.titles.insert_one(doc)
                added += 1
                print(f"  ✓ Added ({ttype}): {title_en}")
            except Exception as e:
                print(f"  ✗ Failed for {name}: {e}")
    return added


async def translate_titles():
    """Batch-translate English titles to Arabic using Claude."""
    titles = await db.titles.find(
        {"$or": [{"title_ar": ""}, {"title_ar": None}]},
        {"_id": 0, "id": 1, "title": 1}
    ).to_list(5000)
    print(f"Translating {len(titles)} titles to Arabic via Claude...")
    BATCH = 30
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"translate-{uuid.uuid4()}",
        system_message=(
            "You translate manga/manhwa titles from English (often Romanized Japanese/Korean) "
            "into natural Arabic. Output ONLY a JSON array of translations matching the input order. "
            "Keep proper names (characters) transliterated phonetically into Arabic. "
            "Don't add explanations or English. Be concise."
        ),
    ).with_model("anthropic", "claude-sonnet-4-6")

    translated = 0
    for i in range(0, len(titles), BATCH):
        batch = titles[i:i + BATCH]
        prompt = (
            "ترجم العناوين التالية إلى عربية بصيغة JSON array of strings فقط (لا شرح):\n\n"
            + "\n".join(f'{idx+1}. "{t["title"]}"' for idx, t in enumerate(batch))
            + "\n\nأرجِع فقط JSON array بحجم " + str(len(batch)) + " بدون ```."
        )
        try:
            resp = await chat.send_message(UserMessage(text=prompt))
            import json
            import re
            txt = resp.strip()
            m = re.search(r"\[.*\]", txt, re.DOTALL)
            if not m:
                print(f"  ! batch {i//BATCH+1}: no JSON found in response")
                continue
            arr = json.loads(m.group(0))
            if len(arr) != len(batch):
                print(f"  ! batch {i//BATCH+1}: mismatch {len(arr)} vs {len(batch)}")
            for t, ar in zip(batch, arr):
                if ar and isinstance(ar, str):
                    await db.titles.update_one({"id": t["id"]}, {"$set": {"title_ar": ar.strip()}})
                    translated += 1
            print(f"  ✓ Batch {i//BATCH+1}/{(len(titles)+BATCH-1)//BATCH} done ({translated} total)")
        except Exception as e:
            print(f"  ! batch {i//BATCH+1} failed: {e}")
    return translated


async def main():
    print("=== Step 1: Importing popular missing titles ===")
    added = await import_popular()
    print(f"Added {added} new titles\n")

    print("=== Step 2: Translating titles to Arabic ===")
    n = await translate_titles()
    print(f"Translated {n} titles\n")

    print("=== Final stats ===")
    print(f"Total visible: {await db.titles.count_documents({'has_chapters': True})}")
    print(f"With Arabic title: {await db.titles.count_documents({'has_chapters': True, 'title_ar': {'$nin': ['', None]}})}")


if __name__ == "__main__":
    asyncio.run(main())
