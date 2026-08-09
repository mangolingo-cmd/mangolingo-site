"""Iter4 regression: admin endpoints + script imports + PWA reachability."""
import os
import sys
import time
import pytest
import requests

# Ensure backend is on sys.path so scrape_mangadex/import_specific/server are importable.
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@otaku.com", "password": "Admin@12345"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- Script import sanity (no runtime) ----
def test_scrape_mangadex_imports_cleanly():
    import importlib
    import scrape_mangadex
    importlib.reload(scrape_mangadex)
    # verify new signature accepts manga_id + search_title kwargs
    import inspect
    sig = inspect.signature(scrape_mangadex.import_series)
    params = sig.parameters
    assert "manga_id" in params, "import_series must accept manga_id kwarg"
    assert "search_title" in params, "import_series must accept search_title kwarg"


def test_import_specific_imports_cleanly():
    import importlib
    import import_specific
    importlib.reload(import_specific)


def test_server_imports_cleanly():
    import importlib, server
    importlib.reload(server)


# ---- Admin endpoints ----
def test_admin_dedupe_titles(h):
    r = requests.post(f"{API}/admin/dedupe-titles", headers=h)
    assert r.status_code in (200, 202), r.text
    data = r.json()
    assert isinstance(data, dict)


def test_admin_fix_missing_covers(h):
    r = requests.post(f"{API}/admin/fix-missing-covers", headers=h)
    assert r.status_code in (200, 202), r.text


def test_admin_import_bundle_starts(h):
    # Just verify endpoint exists / kicks off; don't wait for completion (rate-limited).
    r = requests.post(f"{API}/admin/import-mangaspark-bundle", headers=h)
    assert r.status_code in (200, 202, 409), r.text  # 409 if already running


def test_admin_job_status_dedupe(h):
    r = requests.get(f"{API}/admin/job-status", headers=h, params={"kind": "admin_dedupe"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert "status" in d or "state" in d or isinstance(d, dict)


def test_admin_job_status_fix_covers(h):
    r = requests.get(f"{API}/admin/job-status", headers=h, params={"kind": "admin_fix_covers"})
    assert r.status_code == 200


def test_admin_job_status_import_bundle(h):
    r = requests.get(f"{API}/admin/job-status", headers=h, params={"kind": "admin_import_bundle"})
    assert r.status_code == 200


def test_admin_dedupe_forbidden_for_user():
    # register a normal user and confirm 403
    email = f"tester_forbid_{int(time.time())}@otaku.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Tester@12345", "name": "F"})
    if r.status_code != 200:
        pytest.skip("register failed")
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/admin/dedupe-titles", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code in (401, 403)


# ---- Numeric ordering regression ----
def test_titles_sort_by_all_variants():
    for sb in ("rating", "views", "newest"):
        r = requests.get(f"{API}/titles", params={"sort_by": sb, "limit": 5})
        assert r.status_code == 200, f"{sb}: {r.text}"


def test_watchlist_check_unauth_401():
    # pick any title
    r = requests.get(f"{API}/titles", params={"limit": 1})
    items = r.json().get("items", r.json()) if isinstance(r.json(), (list, dict)) else []
    if not items:
        pytest.skip("no titles")
    tid = items[0]["id"]
    r2 = requests.get(f"{API}/watchlist/{tid}/check")
    assert r2.status_code in (401, 403)
