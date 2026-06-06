"""Scrape popular manhwa from manga-spark.net into MongoDB.

Usage: python3 /app/backend/scrape_mangaspark.py
Imports: titles + episodes with page-image URLs. Images served via /api/proxy/image.
"""
import asyncio
import os
import re
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
import httpx

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

# Curated list of popular slugs on manga-spark.net (manhwa/manhua)
POPULAR_SLUGS = [
    # First batch (15 — already imported)
    "villain-is-here",
    "chronicles-of-the-demon-faction",
    "mount-hua-sects-greatest-genius",
    "i-saw-a-play",
    "magic-academys-genius-blinker",
    "the-great-mage-of-the-heros-party-reincarnates",
    "the-divine-demons-grand-ascension",
    "my-childhood-friends-are-trying-to-kill-me",
    "underworld-restaurant",
    "rebellious-romance",
    "100-days-of-parallel-lines",
    "like-a-chilling-flame",
    "i-pretended-to-be-pregnant-but-my-husband-came-back",
    "i-got-a-job-at-a-spooky-manor",
    "on-a-perfect-revenge",
    # Second batch — additional popular titles
    "tougen-anki",
    "one-punch-man",
    "hajime-no-ippo",
    "magic-emperor",
    "tower-of-god-urek-mazino",
    "solo-farming-in-the-tower",
    "heavenly-demon-cultivation-simulation",
    "reborn-as-the-heavenly-demon",
    "the-supreme-martial-academy",
    "the-sword-emperor-who-surpasses-his-previous-life",
    "the-necromancer-of-a-swordsmanship-family",
    "the-mad-dog-of-the-dukes-estate",
    "grand-duke-of-the-north",
    "miss-pendleton",
    "can-i-cry-now",
    "the-invisible-one",
    "between-your-letter-and-my-reply",
    "i-killed-an-academy-player",
    "battle-mage-farmer",
    "fog-land",
    "memoir-of-the-legendary-scholar",
    "regressed-genius-creates-mythic-items",
    "golden-martial-god",
    "national-level-dungeon-architect",
    "the-glutton",
    "limit-breaking-genius-mage",
    "paranoid-mage",
    "trauma-center",
    "shadow-of-the-reborn-rogues-dominion",
    "return-of-the-devourer",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SOURCE = "mangaspark"


def parse_series_html(html: str, slug: str) -> dict | None:
    """Extract title, cover, description, manga_id, genres from a series page."""
    # manga_id used by AJAX
    m = re.search(r'"manga_id"\s*:\s*"?(\d+)"?', html)
    if not m:
        return None
    manga_id = m.group(1)
    # Title — H1 inside post-title
    title_m = re.search(r'<div class="post-title">\s*<h1>\s*([^<]+?)\s*(?:<span|</h1>)', html, re.S)
    title = title_m.group(1).strip() if title_m else slug.replace("-", " ").title()
    # Description (Arabic story <p>)
    desc_m = re.search(r'<div class="story">\s*<p>\s*(.+?)\s*</p>', html, re.S)
    desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
    # Cover image (og:image is reliable)
    cov_m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    cover = cov_m.group(1) if cov_m else ""
    # Genres
    genres = re.findall(r'class="genres-content"[^>]*>(.+?)</div>', html, re.S)
    genre_list: list[str] = []
    if genres:
        genre_list = [g.strip() for g in re.findall(r'>([^<>]+?)</a>', genres[0]) if g.strip()]
    return {
        "manga_id": manga_id,
        "title": title,
        "title_ar": title,  # will keep same; manga-spark serves Arabic titles
        "description": desc,
        "cover_url": cover,
        "genres": genre_list[:6],
    }


async def fetch_chapters(client: httpx.AsyncClient, slug: str, manga_id: str) -> list[dict]:
    """Return list of {number, url} ordered ascending."""
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
    """Extract image URLs from a chapter page."""
    try:
        r = await client.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return []
        # src attribute on manga-spark has whitespace before URL: src=" \n\t https://...jpg" class="wp-manga-chapter-img"
        raw = re.findall(r'src="\s*([^"]+?)\s*"\s+class="wp-manga-chapter-img"', r.text, re.S)
        return [u.strip() for u in raw if u.strip().startswith("http")]
    except Exception:
        return []


async def import_series(client: httpx.AsyncClient, slug: str, max_chapters: int = 30) -> dict:
    print(f"\n[*] {slug}")
    # Skip if already imported
    existing = await db.titles.find_one({"source": SOURCE, "source_slug": slug})
    if existing:
        print("    already imported, skipping")
        return {"skipped": True}
    try:
        r = await client.get(f"https://manga-spark.net/manga/{slug}/", headers=HEADERS, timeout=30)
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
        "description": info["description"],
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
    chapters = chapters[:max_chapters]  # cap to avoid huge imports
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
        await asyncio.sleep(0.4)  # be polite
    print(f"    + {ep_inserted} chapters imported")
    return {"chapters": ep_inserted, "title": info["title"]}


async def refresh_all_chapters(max_titles: int | None = None, per_title_delay: float = 0.3) -> dict:
    """For every imported manga-spark title, fetch latest chapter list and import any new chapters.
    Returns stats {titles_scanned, new_chapters}."""
    new_chapters = 0
    scanned = 0
    cursor = db.titles.find({"source": SOURCE}, {"id": 1, "source_slug": 1})
    titles = await cursor.to_list(None)
    if max_titles:
        titles = titles[:max_titles]
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for t in titles:
            slug = t["source_slug"]
            tid = t["id"]
            scanned += 1
            # Re-fetch series page to get manga_id (could be cached, but cheap enough)
            try:
                r = await client.get(f"https://manga-spark.net/manga/{slug}/", headers=HEADERS)
                r.raise_for_status()
                info = parse_series_html(r.text, slug)
                if not info:
                    continue
                chapters = await fetch_chapters(client, slug, info["manga_id"])
                if not chapters:
                    continue
                # Find chapter numbers already stored
                existing = await db.episodes.find({"title_id": tid, "source": SOURCE}, {"number": 1}).to_list(None)
                have = {int(e["number"]) for e in existing}
                missing = [c for c in chapters if c["number"] not in have]
                for ch in missing:
                    pages = await fetch_chapter_pages(client, ch["url"])
                    if not pages:
                        continue
                    await db.episodes.insert_one({
                        "id": str(uuid.uuid4()),
                        "title_id": tid,
                        "number": ch["number"],
                        "name": f"الفصل {ch['number']}",
                        "language": "ar",
                        "pages": pages,
                        "source": SOURCE,
                        "source_url": ch["url"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    new_chapters += 1
                    await asyncio.sleep(per_title_delay)
            except Exception as e:
                print(f"[refresh] {slug} failed: {e}")
                continue
            await asyncio.sleep(per_title_delay)
    return {"titles_scanned": scanned, "new_chapters": new_chapters}


async def main():
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        total_titles = 0
        total_chapters = 0
        for slug in POPULAR_SLUGS:
            res = await import_series(client, slug, max_chapters=25)
            if res.get("chapters"):
                total_titles += 1
                total_chapters += res["chapters"]
            await asyncio.sleep(1.0)
        print(f"\nDONE. {total_titles} titles, {total_chapters} chapters total.")


if __name__ == "__main__":
    asyncio.run(main())
