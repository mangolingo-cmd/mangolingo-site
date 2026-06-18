"""One-shot dedupe: merge duplicate titles (same source_slug) and orphan stale ones.

Strategy:
  1. Group titles by source_slug (if present) or by lowercased (title+type).
  2. Keep the entry with the most episodes (tiebreak: oldest created_at).
  3. For each duplicate: re-point its episodes to the keeper, merge unique
     chapter (number, language) pairs, drop the rest, then delete the duplicate
     title doc.
  4. Migrate any watchlist / reviews / reading_progress that reference the dupe
     title_id to the keeper.
  5. Finally drop titles with 0 episodes that share a name with one that has
     episodes.
"""
import asyncio
import os
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def episodes_count(tid: str) -> int:
    return await db.episodes.count_documents({"title_id": tid})


async def merge_into(keeper_id: str, dupe_id: str):
    """Merge a dupe title into keeper: move unique episodes, migrate references, delete dupe."""
    # Build set of (number, language) already in keeper
    existing = set()
    async for ep in db.episodes.find({"title_id": keeper_id}, {"number": 1, "language": 1}):
        existing.add((ep.get("number"), ep.get("language", "ar")))

    moved = 0
    dropped = 0
    async for ep in db.episodes.find({"title_id": dupe_id}):
        key = (ep.get("number"), ep.get("language", "ar"))
        if key in existing:
            await db.episodes.delete_one({"_id": ep["_id"]})
            dropped += 1
        else:
            await db.episodes.update_one({"_id": ep["_id"]}, {"$set": {"title_id": keeper_id}})
            existing.add(key)
            moved += 1

    # Migrate references
    await db.watchlist.update_many({"title_id": dupe_id}, {"$set": {"title_id": keeper_id}})
    await db.reviews.update_many({"title_id": dupe_id}, {"$set": {"title_id": keeper_id}})
    await db.reading_progress.update_many({"title_id": dupe_id}, {"$set": {"title_id": keeper_id}})

    # Delete dupe title
    await db.titles.delete_one({"id": dupe_id})
    return moved, dropped


async def main():
    print("--- Loading titles ---")
    titles = await db.titles.find({}, {"_id": 0}).to_list(length=None)
    print(f"  total titles: {len(titles)}")

    # Group: prefer source_slug+type, fallback (slug-equivalent) on lowercased title+type
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for t in titles:
        slug = (t.get("source_slug") or "").strip().lower()
        ttype = (t.get("type") or "").strip().lower()
        title_norm = (t.get("title") or "").strip().lower()
        key = (slug, ttype) if slug else (f"name:{title_norm}", ttype)
        groups[key].append(t)

    dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"  duplicate groups: {len(dupe_groups)}")

    total_merged = 0
    total_dropped = 0
    total_titles_removed = 0
    for key, items in dupe_groups.items():
        # Get episode counts and pick keeper
        counts = []
        for t in items:
            counts.append((await episodes_count(t["id"]), t))
        counts.sort(key=lambda x: (-x[0], x[1].get("created_at", "")))  # most chapters first
        keeper = counts[0][1]
        keeper_eps = counts[0][0]
        print(f"\n[{key}] keep {keeper['id'][:8]} ({keeper_eps} eps) — '{keeper.get('title','?')[:40]}'")
        for cnt, dupe in counts[1:]:
            print(f"  merge dupe {dupe['id'][:8]} ({cnt} eps) → keeper")
            moved, dropped = await merge_into(keeper["id"], dupe["id"])
            total_merged += moved
            total_dropped += dropped
            total_titles_removed += 1
            print(f"    moved={moved}  dropped(duplicate chapters)={dropped}")

    print("\n--- DONE ---")
    print(f"  titles removed: {total_titles_removed}")
    print(f"  chapters moved: {total_merged}")
    print(f"  duplicate chapters dropped: {total_dropped}")
    print(f"  titles remaining: {await db.titles.count_documents({})}")
    print(f"  episodes remaining: {await db.episodes.count_documents({})}")


if __name__ == "__main__":
    asyncio.run(main())
