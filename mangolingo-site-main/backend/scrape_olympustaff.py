"""Scraper for olympustaff.com (Arabic scanlation team site).
Replaces the dead manga-spark.net as the Arabic chapters source."""
import asyncio
import re
import uuid
from datetime import datetime, timezone

from curl_cffi import requests as curl_requests

BASE = "https://olympustaff.com"
SOURCE = "olympustaff"
MIN_VALID_PAGES = 3

GENRE_MAP = {
    "أكشن": "Action", "اكشن": "Action", "مغامرة": "Adventure", "مغامرات": "Adventure",
    "فانتازيا": "Fantasy", "فنون قتال": "Martial Arts", "قتال": "Martial Arts",
    "دراما": "Drama", "كوميديا": "Comedy", "كوميدي": "Comedy",
    "رومانسي": "Romance", "رومانسية": "Romance", "خيال علمي": "Sci-Fi",
    "غموض": "Mystery", "رعب": "Horror", "نفسي": "Psychological",
    "حياة مدرسية": "School Life", "مدرسي": "School Life", "تاريخي": "Historical",
    "إثارة": "Thriller", "اثارة": "Thriller", "شونين": "Shounen", "سينين": "Seinen",
    "خارق للطبيعة": "Supernatural", "قوى خارقة": "Supernatural", "سحر": "Magic",
    "لعبة": "Game", "ألعاب فيديو": "Video Games", "إيسيكاي": "Isekai",
    "ويب تون": "Webtoons", "دموي": "Gore", "عنف": "Gore", "انتقام": "Revenge",
    "شياطين": "Demons", "وحوش": "Monsters", "إعادة إحياء": "Reincarnation",
}

TYPE_MAP = [("مانهوا", "manhwa"), ("مانها", "manhua"), ("مانجا", "manga")]
STATUS_MAP = [("مستمر", "ongoing"), ("مكتمل", "completed"), ("منتهي", "completed"), ("متوقف", "hiatus")]


def _new_client() -> curl_requests.AsyncSession:
    return curl_requests.AsyncSession(impersonate="chrome", timeout=30)


async def _get_text(client, url: str, attempts: int = 3) -> str | None:
    for i in range(attempts):
        try:
            r = await client.get(url, headers={"Referer": f"{BASE}/"})
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except Exception:
            pass
        await asyncio.sleep(1.5 * (i + 1))
    return None


async def site_alive(url: str = f"{BASE}/", timeout: int = 15) -> bool:
    try:
        async with curl_requests.AsyncSession(impersonate="chrome", timeout=timeout) as c:
            r = await c.get(url)
            return r.status_code == 200
    except Exception:
        return False


def _map_type(text: str) -> str:
    for ar, en in TYPE_MAP:
        if ar in (text or ""):
            return en
    return "manhwa"


def _map_status(text: str) -> str:
    for ar, en in STATUS_MAP:
        if ar in (text or ""):
            return en
    return "ongoing"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9\u0600-\u06FF]+", "", (s or "").lower())


async def list_catalog(client) -> list[dict]:
    """Crawl /series?page=1..N and return [{slug, name, type, status, cover}]."""
    first = await _get_text(client, f"{BASE}/series?page=1")
    if not first:
        return []
    pages = re.findall(r"series\?page=(\d+)", first)
    max_page = max(map(int, pages)) if pages else 1
    entries: dict[str, dict] = {}

    def _parse(html: str):
        for block in html.split('<div class="bsx">')[1:]:
            m = re.search(r'href="' + re.escape(BASE) + r'/series/([^"/]+)"\s+title="([^"]*)"', block)
            if not m:
                continue
            slug, name = m.group(1), m.group(2).strip()
            status = re.search(r'class="status">([^<]*)<', block)
            ttype = re.search(r'class="type">([^<]*)<', block)
            cover = re.search(r'<img[^>]+src="([^"]+)"', block)
            entries[slug] = {
                "slug": slug,
                "name": name,
                "status": _map_status(status.group(1) if status else ""),
                "type": _map_type(ttype.group(1) if ttype else ""),
                "cover": cover.group(1) if cover else "",
            }

    _parse(first)
    for p in range(2, max_page + 1):
        html = await _get_text(client, f"{BASE}/series?page={p}")
        if html:
            _parse(html)
        await asyncio.sleep(0.3)
    return list(entries.values())


async def fetch_series_meta(client, slug: str) -> dict | None:
    html = await _get_text(client, f"{BASE}/series/{slug}")
    if not html:
        return None
    h1 = re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", html)
    og = re.search(r'property="og:image" content="([^"]+)"', html)
    desc = re.search(r'name="description" content="([^"]*)"', html)
    genres = [g.strip() for g in re.findall(r'/series\?genre[^"]*"[^>]*>\s*([^<]+?)\s*<', html)]
    status = re.search(r"(مستمرة|مستمر|مكتملة|مكتمل|منتهي|متوقف)", html)
    return {
        "html": html,
        "title": h1.group(1).strip() if h1 else slug.replace("-", " ").title(),
        "cover": og.group(1) if og else "",
        "synopsis": (desc.group(1) if desc else "").strip(),
        "genres": list(dict.fromkeys(GENRE_MAP.get(g, g) for g in genres if g)),
        "status": _map_status(status.group(1) if status else ""),
    }


def _extract_numbers(html: str, slug: str) -> set[float]:
    return {float(n) for n in re.findall(r'href="' + re.escape(BASE) + "/series/" + re.escape(slug) + r'/(\d+(?:\.\d+)?)"', html)}


async def fetch_chapter_numbers(client, slug: str, first_page_html: str | None = None, max_pages: int = 120) -> set[float]:
    """Full chapter number listing across all chapter-list pages."""
    html = first_page_html or await _get_text(client, f"{BASE}/series/{slug}")
    if not html:
        return set()
    nums = _extract_numbers(html, slug)
    pages = re.findall(re.escape(slug) + r"\?page=(\d+)", html)
    last = min(max(map(int, pages)) if pages else 1, max_pages)
    for p in range(2, last + 1):
        h = await _get_text(client, f"{BASE}/series/{slug}?page={p}")
        if h:
            nums |= _extract_numbers(h, slug)
        await asyncio.sleep(0.25)
    return nums


def _num_str(n: float) -> str:
    return str(int(n)) if n == int(n) else str(n)


async def fetch_chapter_pages(client, slug: str, number: float) -> list[str]:
    html = await _get_text(client, f"{BASE}/series/{slug}/{_num_str(number)}")
    if not html:
        return []
    return re.findall(r'<img[^>]+src="(' + re.escape(BASE) + r'/uploads/[^"]+)"', html)


async def _notify_followers(db, title: dict, ep_doc: dict, number: float):
    try:
        followers = await db.watchlist.find({"title_id": title["id"]}).to_list(None)
        if not followers:
            return
        now = datetime.now(timezone.utc).isoformat()
        await db.notifications.insert_many([
            {
                "id": str(uuid.uuid4()),
                "user_id": f["user_id"],
                "type": "new_chapter",
                "payload": {
                    "title_id": title["id"],
                    "title_name": title.get("title_ar") or title.get("title"),
                    "cover_url": title.get("cover_url"),
                    "episode_id": ep_doc["id"],
                    "episode_number": ep_doc["number"],
                    "language": "ar",
                },
                "read": False,
                "created_at": now,
            }
            for f in followers
        ], ordered=False)
    except Exception:
        pass


async def import_chapter(db, client, title: dict, slug: str, number: float, notify: bool = False) -> bool:
    pages = await fetch_chapter_pages(client, slug, number)
    if len(pages) < MIN_VALID_PAGES:
        return False
    ep = {
        "id": str(uuid.uuid4()),
        "title_id": title["id"],
        "number": int(number) if number == int(number) else number,
        "name": f"الفصل {_num_str(number)}",
        "language": "ar",
        "pages": pages,
        "page_count": len(pages),
        "source": SOURCE,
        "source_url": f"{BASE}/series/{slug}/{_num_str(number)}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.episodes.insert_one(ep)
    await db.titles.update_one(
        {"id": title["id"]},
        {"$set": {"has_chapters": True, "has_ar": True}, "$max": {"last_episode_at": ep["created_at"]}},
    )
    if notify:
        await _notify_followers(db, title, ep, number)
    return True


async def _existing_numbers(db, title_id: str) -> set[float]:
    nums = set()
    async for ep in db.episodes.find({"title_id": title_id}, {"number": 1}):
        try:
            nums.add(float(ep.get("number", -1)))
        except Exception:
            pass
    return nums


async def smart_import(db, progress_cb=None, max_new_titles: int = 10, max_chapters: int = 400) -> dict:
    """Match olympus catalog against existing DB titles (fill missing chapters)
    and import up to `max_new_titles` brand-new titles. Re-runnable/idempotent."""
    stats = {"catalog_total": 0, "scanned": 0, "matched": 0, "new_titles": 0, "chapters_added": 0, "covers_fixed": 0}

    async def _report():
        if progress_cb:
            await progress_cb(dict(stats))

    async with _new_client() as client:
        catalog = await list_catalog(client)
        stats["catalog_total"] = len(catalog)
        await _report()

        # Build normalized lookup of existing titles
        index: dict[str, dict] = {}
        async for t in db.titles.find({}, {"_id": 0, "id": 1, "title": 1, "title_ar": 1, "aliases": 1, "source_slug": 1, "olympus_slug": 1, "cover_url": 1}):
            keys = [t.get("title"), t.get("title_ar"), t.get("source_slug"), t.get("olympus_slug")] + (t.get("aliases") or [])
            for k in keys:
                nk = norm(k)
                if nk and nk not in index:
                    index[nk] = t

        for entry in catalog:
            if stats["chapters_added"] >= max_chapters:
                break
            stats["scanned"] += 1
            slug = entry["slug"]
            match = index.get(norm(slug)) or index.get(norm(entry["name"]))

            if match:
                stats["matched"] += 1
                updates = {}
                if not match.get("olympus_slug"):
                    updates["olympus_slug"] = slug
                cover = match.get("cover_url") or ""
                if (not cover or "manga-spark.net" in cover) and entry.get("cover"):
                    updates["cover_url"] = entry["cover"]
                    stats["covers_fixed"] += 1
                if updates:
                    await db.titles.update_one({"id": match["id"]}, {"$set": updates})
                existing = await _existing_numbers(db, match["id"])
                available = await fetch_chapter_numbers(client, slug)
                missing = sorted(n for n in available if n not in existing)
                for n in missing:
                    if stats["chapters_added"] >= max_chapters:
                        break
                    if await import_chapter(db, client, match, slug, n):
                        stats["chapters_added"] += 1
                    await asyncio.sleep(0.3)
            else:
                if stats["new_titles"] >= max_new_titles:
                    continue
                meta = await fetch_series_meta(client, slug)
                if not meta:
                    continue
                tid = str(uuid.uuid4())
                doc = {
                    "id": tid,
                    "type": entry["type"],
                    "title": meta["title"],
                    "title_ar": "",
                    "synopsis": meta["synopsis"],
                    "cover_url": meta["cover"] or entry.get("cover", ""),
                    "genres": meta["genres"],
                    "status": meta["status"] or entry["status"],
                    "source": SOURCE,
                    "olympus_slug": slug,
                    "source_url": f"{BASE}/series/{slug}",
                    "has_chapters": False,
                    "has_ar": True,
                    "rating_avg": 0,
                    "rating_count": 0,
                    "views_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.titles.insert_one(doc)
                stats["new_titles"] += 1
                for k in (norm(slug), norm(meta["title"])):
                    if k:
                        index[k] = doc
                available = await fetch_chapter_numbers(client, slug, first_page_html=meta["html"])
                inserted_any = False
                for n in sorted(available):
                    if stats["chapters_added"] >= max_chapters:
                        break
                    if await import_chapter(db, client, doc, slug, n):
                        stats["chapters_added"] += 1
                        inserted_any = True
                    await asyncio.sleep(0.3)
                if not inserted_any:
                    await db.titles.update_one({"id": tid}, {"$set": {"has_chapters": False}})
            await _report()
    await _report()
    return stats


async def refresh_latest(db, max_chapters: int = 200) -> dict:
    """Scan DB titles linked to olympus and import newly released chapters
    (first chapter-list page only — where the latest chapters live)."""
    titles_scanned = 0
    new_chapters = 0
    titles = await db.titles.find({"olympus_slug": {"$exists": True, "$nin": [None, ""]}}).to_list(None)
    async with _new_client() as client:
        for t in titles:
            if new_chapters >= max_chapters:
                break
            titles_scanned += 1
            slug = t["olympus_slug"]
            html = await _get_text(client, f"{BASE}/series/{slug}")
            if not html:
                continue
            latest = _extract_numbers(html, slug)
            if not latest:
                continue
            existing = await _existing_numbers(db, t["id"])
            for n in sorted(x for x in latest if x not in existing):
                if new_chapters >= max_chapters:
                    break
                if await import_chapter(db, client, t, slug, n, notify=True):
                    new_chapters += 1
                await asyncio.sleep(0.3)
            await asyncio.sleep(0.3)
    return {"titles_scanned": titles_scanned, "new_chapters": new_chapters}
