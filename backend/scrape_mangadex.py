"""Scrape popular manhwa from MangaDex API into MongoDB.

Usage: python3 /app/backend/scrape_mangadex.py
- Arabic chapters first, English fallback
- Official API - no blocking
"""
import asyncio
import os
import re
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

API = "https://api.mangadex.org"
SOURCE = "mangadex"

POPULAR_SLUGS = [
    "solo-leveling",
    "kill-the-hero",
    "omniscient-readers-viewpoint",
    "the-beginning-after-the-end",
    "mercenary-enrollment",
    "eleceed",
    "legend-of-the-northern-blade",
    "sss-class-suicide-hunter",
    "lookism",
    "tower-of-god",
    "the-greatest-estate-developer",
    "magic-emperor",
    "doom-breaker",
    "reincarnation-of-the-suicidal-battle-god",
    "solo-max-level-newbie",
    "leveling-with-the-gods",
    "pick-me-up-infinite-gacha",
    "second-life-ranker",
    "reaper-of-the-drifting-moon",
    "the-world-after-the-fall",
    "swordmasters-youngest-son",
    "damn-reincarnation",
    "talent-swallowing-magician",
    "murim-login",
    "reincarnation-of-the-veteran-soldier",
    "wind-breaker",
    "overgeared",
    "jungle-juice",
    "the-novel-extra",
    "the-heavenly-demon-cant-live-a-normal-life",
    "return-of-the-mad-demon",
    "trash-of-the-counts-family",
    "tomb-raider-king",
    "the-player-that-cant-level-up",
    "level-up-with-the-gods",
    "absolute-sword-sense",
    "infinite-mage",
    "boundless-necromancer",
    "academy-genius-swordmaster",
    "standard-of-reincarnation",
    "revenge-of-the-iron-blooded-sword-hound",
    "the-dark-mage-returns-after-66666-years",
    "the-king-of-bugs",
    "martial-god-regressed-to-level-2",
    "villain-to-kill",
    "auto-hunting-with-clones",
    "the-s-classes-that-i-raised",
    "dungeon-reset",
]

HEADERS = {
    "User-Agent": "MangaVerse/1.0",
}


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").title()


async def search_manga(client: httpx.AsyncClient, slug: str) -> dict | None:
    title = slug_to_title(slug)
    params = {
        "title": title,
        "limit": 5,
        "includes[]": "cover_art",
        "contentRating[]": ["safe", "suggestive", "erotica"],
        "order[relevance]": "desc",
    }
    try:
        r = await client.get(f"{API}/manga", params=params, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("data", [])
        if not results:
            return None
    # Return first result
        for r in results:
            title_vals = r.get("attributes", {}).get("title", {})
            title_str = " ".join(title_vals.values()).lower()
            if "book version" not in title_str:
                return r
        return results[0] if results else None
    except Exception as e:
        print(f"    ! search failed: {e}")
        return None


def extract_cover(manga: dict) -> str:
    manga_id = manga["id"]
    for rel in manga.get("relationships", []):
        if rel["type"] == "cover_art":
            filename = rel.get("attributes", {}).get("fileName", "")
            if filename:
                return f"https://uploads.mangadex.org/covers/{manga_id}/{filename}"
    return ""


def extract_title(manga: dict) -> tuple[str, str]:
    attrs = manga.get("attributes", {})
    titles = attrs.get("title", {})
    alt_titles = attrs.get("altTitles", [])

    title_en = titles.get("en") or titles.get("ja-ro") or list(titles.values())[0] if titles else ""
    title_ar = ""

    for alt in alt_titles:
        if "ar" in alt:
            title_ar = alt["ar"]
            break

    if not title_ar:
        title_ar = title_en

    return title_en, title_ar


def extract_description(manga: dict) -> str:
    attrs = manga.get("attributes", {})
    desc = attrs.get("description", {})
    return desc.get("ar") or desc.get("en") or ""


def extract_genres(manga: dict) -> list[str]:
    attrs = manga.get("attributes", {})
    tags = attrs.get("tags", [])
    genres = []
    for tag in tags:
        name = tag.get("attributes", {}).get("name", {})
        en_name = name.get("en", "")
        if en_name:
            genres.append(en_name)
    return genres[:6]


async def fetch_chapters(client: httpx.AsyncClient, manga_id: str) -> list[dict]:
    """Fetch chapters - Arabic first, then English fallback."""
    all_chapters = []

    for lang in ["ar", "en"]:
        offset = 0
        while True:
            try:
                params = {
                    "limit": 100,
                    "offset": offset,
                    "translatedLanguage[]": lang,
                    "order[chapter]": "asc",
                    "contentRating[]": ["safe", "suggestive", "erotica"],
                }
                r = await client.get(
                    f"{API}/manga/{manga_id}/feed",
                    params=params,
                    headers=HEADERS,
                    timeout=30
                )
                if r.status_code != 200:
                    break
                data = r.json()
                chapters = data.get("data", [])
                if not chapters:
                    break
                all_chapters.extend([(ch, lang) for ch in chapters])
                total = data.get("total", 0)
                offset += 100
                if offset >= total:
                    break
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"    ! fetch chapters ({lang}) failed: {e}")
                break

        if all_chapters:
            # إذا لقينا عربي، ما نحتاج إنجليزي
            break

    # نظّف وأزل التكرار حسب رقم الفصل
    seen = {}
    result = []
    for ch, lang in all_chapters:
        attrs = ch.get("attributes", {})
        num_str = attrs.get("chapter") or "0"
        try:
            num = float(num_str)
        except:
            continue
        if num not in seen:
            seen[num] = True
            result.append({
                "id": ch["id"],
                "number": num,
                "lang": lang,
            })

    result.sort(key=lambda c: c["number"])
    return result


async def fetch_chapter_pages(client: httpx.AsyncClient, chapter_id: str) -> list[str]:
    try:
        r = await client.get(
            f"{API}/at-home/server/{chapter_id}",
            headers=HEADERS,
            timeout=30
        )
        if r.status_code != 200:
            return []
        data = r.json()
        base_url = data.get("baseUrl", "")
        ch_data = data.get("chapter", {})
        hash_ = ch_data.get("hash", "")
        pages = ch_data.get("data", [])

        urls = [f"{base_url}/data/{hash_}/{p}" for p in pages]
        return urls
    except Exception as e:
        return []


async def import_series(client: httpx.AsyncClient, slug: str) -> dict:
    print(f"\n[*] {slug}")

    existing = await db.titles.find_one({"source": SOURCE, "source_slug": slug})
    if existing:
        print("    already imported, skipping")
        return {"skipped": True}

    # ابحث عن المانهوا في MangaDex
    manga = await search_manga(client, slug)
    if not manga:
        print("    ! not found on MangaDex")
        return {"error": "not found"}

    manga_id = manga["id"]
    title_en, title_ar = extract_title(manga)
    description = extract_description(manga)
    cover = extract_cover(manga)
    genres = extract_genres(manga)

    print(f"    found: {title_en!r} [{manga_id}]")

    # جيب الفصول
    chapters = await fetch_chapters(client, manga_id)
    if not chapters:
        print("    ! no chapters found")
        return {"error": "no chapters"}

    lang_used = chapters[0]["lang"] if chapters else "en"
    print(f"    chapters: {len(chapters)} | lang: {lang_used}")

    title_id = str(uuid.uuid4())
    doc = {
        "id": title_id,
        "type": "manhwa",
        "title": title_en,
        "title_ar": title_ar,
        "synopsis": description,
        "cover_url": cover,
        "genres": genres,
        "status": "ongoing",
        "source": SOURCE,
        "source_slug": slug,
        "source_url": f"https://mangadex.org/title/{manga_id}",
        "has_chapters": True,
        "has_ar": lang_used == "ar",
        "langs_fetched": [lang_used],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.titles.insert_one(doc)

    ep_inserted = 0
    for ch in chapters:
        pages = await fetch_chapter_pages(client, ch["id"])
        if not pages:
            continue

        num = ch["number"]
        ep = {
            "id": str(uuid.uuid4()),
            "title_id": title_id,
            "number": num,
            "name": f"الفصل {int(num) if num == int(num) else num}",
            "language": ch["lang"],
            "pages": pages,
            "source": SOURCE,
            "source_url": f"https://mangadex.org/chapter/{ch['id']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.episodes.insert_one(ep)
        ep_inserted += 1
        await asyncio.sleep(0.3)

    print(f"    + {ep_inserted} chapters imported")
    return {"chapters": ep_inserted, "title": title_en}


async def main():
    total_titles = 0
    total_chapters = 0

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for slug in POPULAR_SLUGS:
            try:
                res = await import_series(client, slug)
                if res and res.get("chapters"):
                    total_titles += 1
                    total_chapters += res["chapters"]
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f"    ! Error processing slug {slug}: {e}")
                await asyncio.sleep(2.0)
                continue

    print(f"\nDONE. {total_titles} titles, {total_chapters} chapters total.")


if __name__ == "__main__":
    asyncio.run(main())