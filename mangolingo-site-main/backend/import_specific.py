"""One-off importer for specific manga slugs.

Usage:
  # MangaSpark (Arabic Mangas)
  python3 import_specific.py <slug1> <slug2> ...

  # MangaDex (English chapters + Arabic when available)
  # Provide slug or slug=MANGADEX_UUID to bypass search
  python3 import_specific.py --source mangadex jujutsu-kaisen \\
      chainsaw-man=a77742b1-befd-49a4-bff5-1ad4e6b0ef7b

  # With alternative search title (when slug->name mapping is bad)
  python3 import_specific.py --source mangadex 'kimetsu-no-yaiba@Demon Slayer'
"""
import asyncio
import sys
import httpx


async def main(args: list[str]):
    source = "mangaspark"
    slugs: list[tuple[str, str | None, str | None]] = []  # (slug, uuid, search_title)
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--source":
            source = args[i + 1]
            i += 2
            continue
        # slug=UUID or slug@Search Title or plain slug
        slug, mid, st = a, None, None
        if "=" in a:
            slug, mid = a.split("=", 1)
        elif "@" in a:
            slug, st = a.split("@", 1)
        slugs.append((slug, mid, st))
        i += 1

    if source == "mangaspark":
        from scrape_mangaspark import import_series as ms_import
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for slug, _, _ in slugs:
                try:
                    res = await ms_import(client, slug, max_chapters=1000)
                    print(f"  result: {res}")
                except Exception as e:
                    print(f"  ! error: {e}")
                await asyncio.sleep(1.5)
    elif source == "mangadex":
        from scrape_mangadex import import_series as md_import
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for slug, mid, st in slugs:
                try:
                    res = await md_import(client, slug, manga_id=mid, search_title=st)
                    print(f"  result: {res}")
                except Exception as e:
                    print(f"  ! error: {e}")
                await asyncio.sleep(1.5)
    else:
        print(f"Unknown source: {source}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1:]))
