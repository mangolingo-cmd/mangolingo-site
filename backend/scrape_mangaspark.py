"""Scrape popular manhwa from manga-spark.net into MongoDB.

Usage: python3 /app/backend/scrape_mangaspark.py
Imports: titles + episodes with page-image URLs. Images served via /api/proxy/image.
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


# القائمة الأسطورية الشاملة للمانهوات المشهورة عالمياً حالياً
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
    "the-star-reclaimed-by-the-unholy",
    "standard-of-reincarnation",
    "revenge-of-the-iron-blooded-sword-hound",
    "the-dark-mage-returns-after-66666-years",
    "the-king-of-bugs",
    "martial-god-regressed-to-level-2",
    "villain-to-kill",
    "auto-hunting-with-clones",
    "the-s-classes-that-i-raised",
    "dungeon-reset"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}

SOURCE = "mangaspark"


def parse_series_html(html: str, slug: str) -> dict | None:
    m = re.search(r'"manga_id"\s*:\s*"?(\d+)"?', html)
    if not m:
        return None
    manga_id = m.group(1)
    title_m = re.search(r'<div class="post-title">\s*<h1>\s*([^<]+?)\s*(?:<span|</h1>)', html, re.S)
    title = title_m.group(1).strip() if title_m else slug.replace("-", " ").title()
    desc_m = re.search(r'<div class="story">\s*<p>\s*(.+?)\s*</p>', html, re.S)
    desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
    cov_m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    cover = cov_m.group(1) if cov_m else ""
    genres = re.findall(r'class="genres-content"[^>]*>(.+?)</div>', html, re.S)
    genre_list: list[str] = []
    if genres:
            genre_list = [g.strip() for g in re.findall(r'>([^<>]+?)</a>', genres[0]) if g.strip()]
    return {
        "manga_id": manga_id,
        "title": title,
        "title_ar": title,
        "description": desc,
        "cover_url": cover,
        "genres": genre_list[:6],
    }
async def fetch_chapters(client: httpx.AsyncClient, slug: str, manga_id: str) -> list[dict]:
    r = await client.post(
        "https://manga-spark.net/wp-admin/admin-ajax.php",
        data={"action": "manga_get_chapters", "manga": manga_id},
        headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
    )

    if r.status_code != 200:
        return []
    chap_urls = re.findall(rf'href="(https://manga-spark\.net/manga/{re.escape(slug)}/([0-9]+)/?)"', r.text)

    seen: set[str] = set()
    chapters: list[dict] = []
    for url, num in chap_urls:
        if num in seen:
            continue
        seen.add(num)
        chapters.append({"number": int(num), "url": url})
    chapters.sort(key=lambda c: c["number"])
    return chapters


async def fetch_chapter_pages(client: httpx.AsyncClient, url: str) -> list[str]:
    try:
        chapter_headers = {**HEADERS, "Referer": url}
        r = await client.get(url, headers=chapter_headers, timeout=30)
        if r.status_code != 200:
            return []
        pages = []
        img_tags = re.findall(r'<img[^>]+>', r.text, re.S)
        for img in img_tags:
            if 'wp-manga-chapter-img' not in img:
                continue
            src_m = re.search(r'data-lazy-src="([^"]+)"', img)
            if not src_m:
                src_m = re.search(r'data-src="([^"]+)"', img)
            if not src_m:
                src_m = re.search(r'\bsrc="([^"]+)"', img)
            if src_m:
                src = src_m.group(1).strip()
                if src.startswith("http"):
                    pages.append(src)
        return pages
    except Exception:
        return []


async def import_series(client: httpx.AsyncClient, slug: str, max_chapters: int = 1000) -> dict:
    print(f"\n[*] {slug}")
    await asyncio.sleep(1.0)
    
    existing = await db.titles.find_one({"source": SOURCE, "source_slug": slug})
    if existing:
        print("    already imported, skipping")
        return {"skipped": True}

    try:
        r = await client.get(f"https://manga-spark.net/manga/{slug}/", headers={**HEADERS, "Referer": "https://manga-spark.net"}, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"    ! fetch series failed: {e}")
        return {"error": str(e)}

    info = parse_series_html(r.text, slug)
    if not info:
        print("    ! parse failed")
        return {"error": "parse"}

    title_id = str(uuid.uuid4())
    doc = {
        "id": title_id,
        "type": "manhwa",
        "title": info["title"],
        "title_ar": info["title_ar"],
        "synopsis": info["description"],
        "cover_url": info["cover_url"],
        "genres": info["genres"],
        "status": "ongoing",
        "source": SOURCE,
        "source_slug": slug,
        "source_url": f"https://manga-spark.net/manga/{slug}/",
        "has_chapters": True,
        "has_ar": True,
        "langs_fetched": ["ar"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    chapters = await fetch_chapters(client, slug, info["manga_id"])
    if not chapters:
        print("    ! no chapters")
        return {"error": "no chapters"}
    chapters = chapters[:max_chapters]
    print(f"    title: {info['title']!r} | chapters: {len(chapters)}")
    await db.titles.insert_one(doc)
    ep_inserted = 0
    for ch in chapters:
        pages = await fetch_chapter_pages(client, ch["url"])
        if not pages:
            continue
        ep = {
            "id": str(uuid.uuid4()),
                            "title_id": title_id,
            "number": ch["number"],
            "name": f"الفصل {ch['number']}",
            "language": "ar",
            "pages": pages,
            "source": SOURCE,
            "source_url": ch["url"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.episodes.insert_one(ep)
        ep_inserted += 1
        await asyncio.sleep(0.2)
    print(f"    + {ep_inserted} chapters imported")
    return {"chapters": ep_inserted, "title": info["title"]}


async def refresh_all_chapters() -> dict:
    """Scan all manga-spark titles already in DB and import any new chapters.

    Returns stats: { titles_scanned, new_chapters }.
    """
    titles_scanned = 0
    new_chapters = 0
    cursor = db.titles.find({"source": SOURCE, "source_slug": {"$exists": True, "$ne": None}})
    titles = await cursor.to_list(length=None)
    transport = httpx.AsyncHTTPTransport(retries=2)
    async with httpx.AsyncClient(transport=transport, timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for t in titles:
            titles_scanned += 1
            slug = t.get("source_slug")
            try:
                r = await client.get(f"https://manga-spark.net/manga/{slug}/", headers={**HEADERS, "Referer": "https://manga-spark.net"})
                if r.status_code != 200:
                    continue
                info = parse_series_html(r.text, slug)
                if not info:
                    continue
                chapters = await fetch_chapters(client, slug, info["manga_id"])
                if not chapters:
                    continue
                existing_nums = set()
                async for ep in db.episodes.find({"title_id": t["id"]}, {"number": 1}):
                    try:
                        existing_nums.add(int(ep.get("number", -1)))
                    except Exception:
                        pass
                for ch in chapters:
                    if ch["number"] in existing_nums:
                        continue
                    pages = await fetch_chapter_pages(client, ch["url"])
                    if not pages:
                        continue
                    await db.episodes.insert_one({
                        "id": str(uuid.uuid4()),
                        "title_id": t["id"],
                        "number": ch["number"],
                        "name": f"الفصل {ch['number']}",
                        "language": "ar",
                        "pages": pages,
                        "source": SOURCE,
                        "source_url": ch["url"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    new_chapters += 1
                    await asyncio.sleep(0.3)
            except Exception as e:
                print(f"refresh error for {slug}: {e}")
                continue
            await asyncio.sleep(1.0)
    return {"titles_scanned": titles_scanned, "new_chapters": new_chapters}


async def main():
    total_titles = 0
    total_chapters = 0
    for slug in POPULAR_SLUGS:
        try:
            transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=3)
            async with httpx.AsyncClient(transport=transport, timeout=30, follow_redirects=True) as client:
                res = await import_series(client, slug, max_chapters=1000)
                if res and res.get("chapters"):
                    total_titles += 1
                    total_chapters += res["chapters"]
                await asyncio.sleep(1.5)
        except Exception as e:
            print(f"    ! Error processing slug {slug}: {e}")
            await asyncio.sleep(3.0)
            continue
            
    print(f"\nDONE. {total_titles} titles, {total_chapters} chapters total.")



if __name__ == "__main__":
    asyncio.run(main())
