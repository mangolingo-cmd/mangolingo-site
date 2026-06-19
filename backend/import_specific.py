"""One-off importer for specific manga-spark slugs.

Usage: python3 import_specific.py slug1 slug2 ...
"""
import asyncio
import sys
import httpx
from scrape_mangaspark import import_series


async def main(slugs: list[str]):
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=3)
    async with httpx.AsyncClient(transport=transport, timeout=30, follow_redirects=True) as client:
        for slug in slugs:
            try:
                res = await import_series(client, slug, max_chapters=1000)
                print(f"  result: {res}")
            except Exception as e:
                print(f"  ! error: {e}")
            await asyncio.sleep(1.5)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 import_specific.py slug1 slug2 ...")
        sys.exit(1)
    asyncio.run(main(sys.argv[1:]))
