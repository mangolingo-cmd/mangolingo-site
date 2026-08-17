"""Scrape popular manhwa/manga from sparkmanga.net into MongoDB.

Uses curl_cffi.AsyncSession with browser TLS/JA3 fingerprinting to bypass
Cloudflare protection. Provides:
  • import_series(client, slug, max_chapters)  — one-off import
  • refresh_all_chapters(db_arg=None)          — background loop (accepts an
                                                 optional db instance from the
                                                 API side; falls back to module
                                                 db when omitted)

Usage (CLI):   python3 /app/backend/scrape_mangaspark.py
"""
import asyncio
import os
import re
import uuid
from datetime import datetime, timezone

from curl_cffi import requests as curl_requests  # sync + AsyncSession
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

#load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "otaku_hub")
db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]

# ---------------------------------------------------------------------------
# Popular slug list. Add new slugs at the bottom; existing ones dedup by slug.
# ---------------------------------------------------------------------------
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
    "build-up",
    "magic-emperor",
    "doom-breaker",
    "reincarnation-of-the-suicidal-battle-god",
    "solo-max-level-newbie",
    "leveling-with-the-gods",
    "pick-me-up",
    "ranker-who-lives-a-second-time",
    "the-world-after-the-fall",
    "the-novel-extra",
    "tomb-raider-king",
    "the-player-that-cant-level-up",
    "level-up-with-the-gods",
    "boundless-necromancer",
    "academy-genius-swordmaster",
    "academys-genius-swordmaster",
    "the-star-reclaimed-by-the-unholy",
    "the-dark-mage-returns-after-66666-years",
    "return-of-the-mad-demon",
    "the-king-of-bugs",
    "manager-kim",
    "the-s-classes-that-i-raised",
    "dungeon-reset",
    "top-tier-providence-secretly-cultivate-for-a-thousand-years",
    "the-god-of-high-school",
    "bleach-official-colored",
    "dragon-ball-super",
    "boruto-naruto-next-generations",
    "one-piece",
    # -------- 2026-02 batch (user-requested backfill) --------
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
    "top-corner",
    "against-the-gods",
    "jujutsu-kaisen",
    "spy-x-family",
    "black-clover",
    "the-eminence-in-shadow",
    "tenseisei-shitara-slime-datta-ken",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Referer": "https://sparkmanga.net/",
    "Connection": "keep-alive",
}

SOURCE = "mangaspark"
MIN_VALID_PAGES = 3  # skip chapters with fewer pages (probably incomplete)


# ---------------------------------------------------------------------------
# curl_cffi helpers (Cloudflare TLS/JA3 bypass)
# ---------------------------------------------------------------------------
def _new_client() -> curl_requests.AsyncSession:
    """Return a fresh async curl_cffi session impersonating Chrome (bypasses CF)."""
    return curl_requests.AsyncSession(impersonate="chrome", timeout=30)


async def _request_with_retry(client, url: str, *, max_attempts: int = 4, extra_headers: dict | None = None):
    """GET with exponential backoff (0.5s, 1s, 2s, 4s). Returns Response or raises."""
    headers = {**HEADERS, **(extra_headers or {})}
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            r = await client.get(url, headers=headers)
            if r.status_code >= 500 or r.status_code == 429:
                raise RuntimeError(f"http {r.status_code}")
            return r
        except Exception as e:
            last_exc = e
            if attempt == max_attempts - 1:
                break
            backoff = 0.5 * (2 ** attempt)
            print(f"      retry {attempt + 1}/{max_attempts} after {backoff:.1f}s ({type(e).__name__})")
            await asyncio.sleep(backoff)
    raise last_exc if last_exc else RuntimeError("retry failed")


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------
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
        "genres": genre_list,
    }


async def fetch_chapters(client, slug: str, manga_id: str) -> list[dict]:
    """POST to /wp-admin/admin-ajax.php get_chapters endpoint, then parse links."""
    try:
        r = await client.post(
            "https://sparkmanga.net/wp-admin/admin-ajax.php",
            data={"action": "manga_get_chapters", "manga": manga_id},
            headers={
                **HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://sparkmanga.net/manga/{slug}/",
            },
        )
        if r.status_code != 200:
            return []
        text = r.text
    except Exception as e:
        print(f"      ! fetch chapters failed: {e}")
        return []

   chap_urls = re.findall(
    rf'href="(https://(?:manga-spark\.net|sparkmanga\.net)/manga/{re.escape(slug)}/([0-9]+)/?)"',
    text
)
    seen: set[str] = set()
    chapters: list[dict] = []
    for url, num in chap_urls:
        if num in seen:
            continue
        seen.add(num)
        chapters.append({"number": int(num), "url": url})
    chapters.sort(key=lambda c: c["number"])
    return chapters


async def fetch_chapter_pages(client, url: str) -> list[str]:
    try:
        r = await _request_with_retry(client, url, extra_headers={"Referer": url})
        if r.status_code != 200:
            return []
        pages: list[str] = []
        for img in re.findall(r'<img[^>]+>', r.text, re.S):
            if 'wp-manga-chapter-img' not in img:
                continue
            src_m = re.search(r'data-lazy-src="([^"]+)"', img) or re.search(
                r'data-src="([^"]+)"', img
            ) or re.search(r'\bsrc="([^"]+)"', img)
            if src_m:
                src = src_m.group(1).strip()
                if src.startswith("http"):
                    pages.append(src)
        return pages
    except Exception as e:
        print(f"      ! pages fetch error after retries: {e}")
        return []


# ---------------------------------------------------------------------------
# Main import primitives
# ---------------------------------------------------------------------------
async def import_series(client, slug: str, max_chapters: int = 1000) -> dict:
    print(f"\n[*] {slug}")
    await asyncio.sleep(0.5)

    existing = await db.titles.find_one({"source": SOURCE, "source_slug": slug})
    if existing:
        eps = await db.episodes.count_documents({"title_id": existing["id"]})
        print(f"    already imported ({eps} chapters), skipping")
        return {"skipped": True, "chapters": eps}

    try:
        r = await _request_with_retry(client, f"https://sparkmanga.net/manga/{slug}/")
        if r.status_code != 200:
            print(f"    ! HTTP {r.status_code}")
            return {"error": f"http {r.status_code}"}
    except Exception as e:
        print(f"    ! fetch series failed: {e}")
        return {"error": str(e)}

    info = parse_series_html(r.text, slug)
    if not info:
        print("    ! parse failed (slug not on sparkmanga.net)")
        return {"error": "parse"}

    chapters = await fetch_chapters(client, slug, info["manga_id"])
    if not chapters:
        print("    ! no chapters found")
        return {"error": "no chapters"}
    chapters = chapters[:max_chapters]

    print(f"    title: {info['title']!r} | chapters: {len(chapters)}")
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
        "source_url": f"https://sparkmanga.net/manga/{slug}/",
        "has_chapters": True,
        "has_ar": True,
        "langs_fetched": ["ar"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.titles.insert_one(doc)

    ep_inserted = 0
    ep_skipped = 0
    for ch in chapters:
        pages = await fetch_chapter_pages(client, ch["url"])
        if len(pages) < MIN_VALID_PAGES or not all(p.startswith("http") for p in pages):
            ep_skipped += 1
            continue
        ep = {
            "id": str(uuid.uuid4()),
            "title_id": title_id,
            "number": ch["number"],
            "name": f"الفصل {ch['number']}",
            "language": "ar",
            "pages": pages,
            "page_count": len(pages),
            "source": SOURCE,
            "source_url": ch["url"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.episodes.insert_one(ep)
        await db.titles.update_one({"id": title_id}, {"$max": {"last_episode_at": ep["created_at"]}})
        ep_inserted += 1
        await asyncio.sleep(0.2)

    if ep_inserted == 0:
        await db.titles.update_one({"id": title_id}, {"$set": {"has_chapters": False}})
    print(f"    + {ep_inserted} chapters imported ({ep_skipped} skipped as incomplete)")
    return {"chapters": ep_inserted, "skipped": ep_skipped, "title": info["title"]}


# ---------------------------------------------------------------------------
# refresh loop used by the background scheduler & the Refresh Now admin button
# ---------------------------------------------------------------------------
async def refresh_all_chapters(db_arg=None) -> dict:
    """Scan every mangaspark title already in DB and import any NEW chapters.

    Accepts an optional Motor DB instance so callers from the API side (which
    hold their own DB reference) can pass it in — matches the historical
    signature the server's background task uses.
    """
    active_db = db_arg if db_arg is not None else db

    titles_scanned = 0
    new_chapters = 0
    cursor = active_db.titles.find(
        {"source": SOURCE, "source_slug": {"$exists": True, "$ne": None}}
    )
    titles = await cursor.to_list(length=None)

    async with _new_client() as client:
        for t in titles:
            titles_scanned += 1
            slug = t.get("source_slug")
            try:
                r = await _request_with_retry(client, f"https://sparkmanga.net/manga/{slug}/")
                if r.status_code != 200:
                    continue
                info = parse_series_html(r.text, slug)
                if not info:
                    continue
                chapters = await fetch_chapters(client, slug, info["manga_id"])
                if not chapters:
                    continue
                existing_nums = set()
                async for ep in active_db.episodes.find(
                    {"title_id": t["id"]}, {"number": 1}
                ):
                    try:
                        existing_nums.add(int(ep.get("number", -1)))
                    except Exception:
                        pass
                for ch in chapters:
                    if ch["number"] in existing_nums:
                        continue
                    pages = await fetch_chapter_pages(client, ch["url"])
                    if len(pages) < MIN_VALID_PAGES:
                        # one more retry on incomplete
                        await asyncio.sleep(1.5)
                        pages = await fetch_chapter_pages(client, ch["url"])
                        if len(pages) < MIN_VALID_PAGES:
                            continue
                    ep_doc = {
                        "id": str(uuid.uuid4()),
                        "title_id": t["id"],
                        "number": ch["number"],
                        "name": f"الفصل {ch['number']}",
                        "language": "ar",
                        "pages": pages,
                        "page_count": len(pages),
                        "source": SOURCE,
                        "source_url": ch["url"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    await active_db.episodes.insert_one(ep_doc)
                    await active_db.titles.update_one({"id": t["id"]}, {"$max": {"last_episode_at": ep_doc["created_at"]}})
                    new_chapters += 1
                    # Fan-out in-app notifications to followers
                    try:
                        followers = await active_db.watchlist.find(
                            {"title_id": t["id"]}
                        ).to_list(None)
                        if followers:
                            now = datetime.now(timezone.utc).isoformat()
                            await active_db.notifications.insert_many([
                                {
                                    "id": str(uuid.uuid4()),
                                    "user_id": f["user_id"],
                                    "type": "new_chapter",
                                    "payload": {
                                        "title_id": t["id"],
                                        "title_name": t.get("title_ar") or t.get("title"),
                                        "cover_url": t.get("cover_url"),
                                        "episode_id": ep_doc["id"],
                                        "episode_number": ch["number"],
                                        "language": "ar",
                                    },
                                    "read": False,
                                    "created_at": now,
                                }
                                for f in followers
                            ], ordered=False)
                    except Exception as ne:
                        print(f"  notify error: {ne}")
                    await asyncio.sleep(0.3)
            except Exception as e:
                print(f"refresh error for {slug}: {e}")
                continue
            await asyncio.sleep(1.0)
    return {"titles_scanned": titles_scanned, "new_chapters": new_chapters}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def main():
    total_titles = 0
    total_chapters = 0
    async with _new_client() as client:
        for slug in POPULAR_SLUGS:
            try:
                res = await import_series(client, slug, max_chapters=1000)
                if res and res.get("chapters"):
                    total_titles += 1
                    total_chapters += res["chapters"]
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"    ! Error processing slug {slug}: {e}")
                await asyncio.sleep(3.0)
    print(f"\nDONE. {total_titles} titles, {total_chapters} chapters total.")


if __name__ == "__main__":
    asyncio.run(main())
