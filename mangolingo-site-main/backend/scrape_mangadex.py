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

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

POPULAR_SLUGS = [
        "ending-maker",
    "chronicles-of-heavenly-demon",
    "fff-class-trashero",
    "hardcore-leveling-warrior",
    "peerless-dad",
    "survival-story-of-a-sword-king-in-a-fantasy-world",
    "the-scholars-reincarnation",
    "worn-and-torn-newbie",
    "star-fostering-swordmaster",
    "eternally-regressing-knight",
    "bastard",
    "shotgun-boy",
    "sweet-home",
    "cheolsu-saves-the-world",
    "the-dungeon-master",
    "the-terminally-ill-young-master-of-the-baek-clan",
    "terminally-ill-genius-dark-knight",
    "berserk",
    "black-clover",
    "my-hero-academia",
    "attack-on-titan",
    "frieren",
    "fullmetal-alchemist",
    "the-eminence-in-shadow",
    "undead-unluck",
    "that-time-i-got-reincarnated-as-a-slime",
    "jojo-bizarre-adventure",
    "naruto",
    "boruto-naruto-next-generations",
    "bleach",
    "dragon-ball",
    "dragon-ball-super",
    # القائمة الجديدة بالكامل مدمجة ومحوّلة إلى IDs رسمية ومباشرة
    "the-indomitable-martial-king",
    "the-knight-king-who-returned-with-a-god",
    "the-max-level-hero-has-returned",
    "the-nebula-s-civilization",
    "necromancers-evolutionary-traits",
    "genius-of-the-unique-lineage",
    "the-lords-coins-of-reincarnation",
    "steel-eating-player",
    "god-of-blackfield",
    "past-life-regressor",
    "infinite-level-up-in-murim",
    "reincarnated-as-an-unruly-heir",
    "worlds-best-assassin",
    "absolute-martial-arts",
    "martial-peak",
    "apocalypse-online",
    "the-challenger",
    "auto-hunting-with-clones",
    "top-corner"
]


HEADERS = {
    "User-Agent": "mangolingo/1.0",
}


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").title()


async def search_manga(client: httpx.AsyncClient, slug: str, override_title: str | None = None) -> dict | None:
    title = override_title or slug_to_title(slug)
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
                await asyncio.sleep(3)
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
        except (ValueError, TypeError):
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


MIN_VALID_PAGES = 3


async def _request_with_retry(client: httpx.AsyncClient, url: str, *, max_attempts: int = 4, **kw):
    """GET with exponential backoff (0.5s, 1s, 2s, 4s). Returns Response or raises."""
    # Only fall back to a browser UA if caller didn't specify one
    kw.setdefault("headers", {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})

    last_exc = None
    for attempt in range(max_attempts):
        try:
            r = await client.get(url, **kw)
            if r.status_code >= 500 or r.status_code == 429:
                raise httpx.HTTPStatusError(f"http {r.status_code}", request=r.request, response=r)
            return r
        except Exception as e:
            last_exc = e
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(0.5 * (2 ** attempt))
    raise last_exc if last_exc else RuntimeError("retry failed")


async def fetch_chapter_pages(client: httpx.AsyncClient, chapter_id: str) -> list[str]:
    try:
        r = await _request_with_retry(
            client,
            f"{API}/at-home/server/{chapter_id}",
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        base_url = data.get("baseUrl", "")
        ch_data = data.get("chapter", {})
        hash_ = ch_data.get("hash", "")
        pages = ch_data.get("data", [])

        urls = [f"{base_url}/data/{hash_}/{p}" for p in pages]
        # Validate: must be ≥ MIN_VALID_PAGES and all https URLs
        if len(urls) < MIN_VALID_PAGES or not all(u.startswith("http") for u in urls):
            return []
        return urls
    except Exception as e:
        print(f"      ! pages fetch error after retries: {e}")
        return []


async def import_series(client: httpx.AsyncClient, slug: str, *, manga_id: str | None = None, search_title: str | None = None) -> dict:
    """Import a title from MangaDex.

    slug         — DB slug (source_slug); required for dedup + re-runs.
    manga_id     — (optional) exact MangaDex UUID; bypasses fuzzy title search.
    search_title — (optional) alternative name used when the slug doesn't map
                    well (e.g. use Japanese romaji when slug is English).
    """
    print(f"\n[*] {slug}")

    existing = await db.titles.find_one({"source": SOURCE, "source_slug": slug})
    if existing:
        eps = await db.episodes.count_documents({"title_id": existing["id"]})
        print(f"    already imported ({eps} chapters), skipping")
        return {"skipped": True, "chapters": eps}

    # 1) Resolve MangaDex manga document
    if manga_id:
        try:
            r = await client.get(f"{API}/manga/{manga_id}", params={"includes[]": "cover_art"}, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"    ! manga_id lookup HTTP {r.status_code}")
                return {"error": f"lookup {r.status_code}"}
            manga = r.json().get("data")
        except Exception as e:
            print(f"    ! manga_id lookup failed: {e}")
            return {"error": str(e)}
    else:
        # Try given search_title first, then fall back to slug-based derivation
        if search_title:
            manga = await _search_by_title(client, search_title)
        else:
            manga = await search_manga(client, slug)
        if not manga:
            print(f"    ! not found on MangaDex (query='{search_title or slug_to_title(slug)}')")
            return {"error": "not found"}

    manga_id = manga["id"]
    title_en, title_ar = extract_title(manga)
    description = extract_description(manga)
    cover = extract_cover(manga)
    genres = extract_genres(manga)

    print(f"    found: {title_en!r} [{manga_id}]")

    chapters = await fetch_chapters(client, manga_id)
    if not chapters:
        print("    ! no chapters found")
        return {"error": "no chapters"}

    lang_used = chapters[0]["lang"] if chapters else "en"
    print(f"    chapters: {len(chapters)} | lang: {lang_used}")

    title_id = str(uuid.uuid4())
    orig_lang = (manga.get("attributes") or {}).get("originalLanguage", "")
    ttype = {"ja": "manga", "ko": "manhwa", "zh": "manhua", "zh-hk": "manhua", "zh-tw": "manhua"}.get(orig_lang, "manhwa")
    doc = {
        "id": title_id,
        "type": ttype,
        "title": title_en,
        "title_ar": title_ar,
        "synopsis": description,
        "cover_url": cover,
        "genres": genres,
        "status": "ongoing",
        "source": SOURCE,
        "source_slug": slug,
        "mangadex_id": manga_id,
        "source_url": f"https://mangadex.org/title/{manga_id}",
        "has_chapters": True,
        "has_ar": lang_used == "ar",
        "langs_fetched": [lang_used],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.titles.insert_one(doc)

    ep_inserted = 0
    ep_skipped = 0
    for ch in chapters:
        pages = await fetch_chapter_pages(client, ch["id"])
        # Validate: min pages + all URLs are absolute
        if len(pages) < MIN_VALID_PAGES or not all(p.startswith("http") for p in pages):
            ep_skipped += 1
            continue

        num = ch["number"]
        ep = {
            "id": str(uuid.uuid4()),
            "title_id": title_id,
            "number": num,
            "name": f"الفصل {int(num) if num == int(num) else num}",
            "language": ch["lang"],
            "pages": pages,
            "page_count": len(pages),
            "source": SOURCE,
            "source_url": f"https://mangadex.org/chapter/{ch['id']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.episodes.insert_one(ep)
        await db.titles.update_one({"id": title_id}, {"$max": {"last_episode_at": ep["created_at"]}})
        ep_inserted += 1
        await asyncio.sleep(3)

    if ep_inserted == 0:
        # Mark as no-chapters so it doesn't show as a ghost entry
        await db.titles.update_one({"id": title_id}, {"$set": {"has_chapters": False}})
    print(f"    + {ep_inserted} chapters imported ({ep_skipped} skipped as incomplete)")
    return {"chapters": ep_inserted, "skipped": ep_skipped, "title": title_en}


async def _search_by_title(client: httpx.AsyncClient, query: str) -> dict | None:
    """Direct title search on MangaDex without slug munging."""
    try:
        r = await client.get(
            f"{API}/manga",
            params={
                "title": query,
                "limit": 5,
                "includes[]": "cover_art",
                "contentRating[]": ["safe", "suggestive", "erotica"],
                "order[relevance]": "desc",
            },
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data", [])
        for item in data:
            t = item.get("attributes", {}).get("title", {})
            t_str = " ".join(t.values()).lower()
            if "book version" not in t_str:
                return item
        return data[0] if data else None
    except Exception:
        return None


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