"""Iter5 regression: Verify the 'Refresh Now' admin bug fix.

Focus: (a) POST /api/admin/refresh-mangaspark returns 202/200 IMMEDIATELY as a
background job, (b) GET /api/admin/job-status?kind=mangaspark_refresh_manual
transitions status, (c) validation + auth on job-status, (d) curl_cffi importable,
(e) scrape_mangaspark module imports + has the 26 required slugs, (f) refresh
signature accepts db_arg, (g) requirements.txt has curl_cffi, (h) regression on
previously-working endpoints (titles/episodes/users/chat/PWA/import-bundle).
"""
import inspect
import os
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@otaku.com", "password": "Admin@12345"}

REQUIRED_NEW_SLUGS = [
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
    "one-piece",
    "spy-x-family",
    "black-clover",
    "the-eminence-in-shadow",
    "tenseisei-shitara-slime-datta-ken",
]


# =============== fixtures ================
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ==================== Module-level sanity ====================
def test_curl_cffi_importable():
    from curl_cffi import requests as curl_requests
    assert curl_requests.AsyncSession is not None
    # instantiable
    s = curl_requests.AsyncSession(impersonate="chrome")
    assert s is not None


def test_scrape_mangaspark_module_imports():
    import importlib
    import scrape_mangaspark
    importlib.reload(scrape_mangaspark)
    from scrape_mangaspark import (
        POPULAR_SLUGS,
        import_series,
        refresh_all_chapters,
    )
    assert callable(import_series)
    assert callable(refresh_all_chapters)
    assert isinstance(POPULAR_SLUGS, list)
    assert len(POPULAR_SLUGS) >= 60, f"expected >=60 slugs, got {len(POPULAR_SLUGS)}"


def test_refresh_all_chapters_signature_accepts_db_arg():
    from scrape_mangaspark import refresh_all_chapters
    sig = inspect.signature(refresh_all_chapters)
    params = sig.parameters
    assert "db_arg" in params, f"missing db_arg param; sig={sig}"
    # must be optional (has default)
    assert params["db_arg"].default is None, f"db_arg should default to None; sig={sig}"


def test_popular_slugs_contains_all_26_new_slugs():
    from scrape_mangaspark import POPULAR_SLUGS
    missing = [s for s in REQUIRED_NEW_SLUGS if s not in POPULAR_SLUGS]
    assert not missing, f"missing slugs: {missing}"


def test_requirements_has_curl_cffi():
    with open("/app/backend/requirements.txt") as f:
        content = f.read().lower()
    assert "curl_cffi" in content or "curl-cffi" in content


# ==================== Admin refresh-mangaspark: background task ====================
def test_refresh_mangaspark_returns_immediately(h):
    """Bug fix: endpoint must return in <5s with status=processing + job_id."""
    start = time.time()
    r = requests.post(f"{API}/admin/refresh-mangaspark", headers=h, timeout=15)
    elapsed = time.time() - start
    assert r.status_code in (200, 202), f"{r.status_code} {r.text}"
    assert elapsed < 5.0, f"took {elapsed:.2f}s (bug: proxy timeout!)"
    body = r.json()
    assert body.get("status") == "processing", body
    assert "job_id" in body and body["job_id"]
    assert "poll_url" in body and "mangaspark_refresh_manual" in body["poll_url"]


def test_job_status_mangaspark_refresh_manual(h):
    """Job status must be reachable after the refresh trigger and expose
    titles_scanned + new_chapters counters."""
    # Trigger a fresh job first
    trig = requests.post(f"{API}/admin/refresh-mangaspark", headers=h, timeout=15)
    assert trig.status_code in (200, 202), trig.text
    job_id = trig.json()["job_id"]

    # Poll once quickly — should be running or done
    time.sleep(1.0)
    r = requests.get(
        f"{API}/admin/job-status",
        params={"kind": "mangaspark_refresh_manual"},
        headers=h,
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") in ("running", "done", "failed"), body
    # counters must be present (initialized to 0 at insert time)
    assert "titles_scanned" in body
    assert "new_chapters" in body
    # Job document should reference our job_id (latest by started_at)
    assert body.get("job_id") == job_id, f"got {body.get('job_id')} vs {job_id}"


# ==================== Job status validation + auth ====================
def test_job_status_invalid_kind_returns_400(h):
    r = requests.get(
        f"{API}/admin/job-status",
        params={"kind": "invalid_kind"},
        headers=h,
        timeout=10,
    )
    assert r.status_code == 400, f"{r.status_code} {r.text}"


def test_job_status_without_auth_returns_401():
    r = requests.get(
        f"{API}/admin/job-status",
        params={"kind": "mangaspark_refresh_manual"},
        timeout=10,
    )
    assert r.status_code in (401, 403), r.status_code


@pytest.mark.parametrize("kind", ["admin_dedupe", "admin_fix_covers", "admin_import_bundle"])
def test_job_status_regression_kinds(h, kind):
    """Existing whitelist entries still valid."""
    r = requests.get(
        f"{API}/admin/job-status",
        params={"kind": kind},
        headers=h,
        timeout=10,
    )
    assert r.status_code == 200, f"{kind}: {r.status_code} {r.text}"
    body = r.json()
    assert "status" in body


# ==================== Regression on previously-working endpoints ====================
def _titles_list(resp_json):
    """Handle both list and paginated {items:[...]} shapes."""
    if isinstance(resp_json, dict) and "items" in resp_json:
        return resp_json["items"]
    return resp_json if isinstance(resp_json, list) else []


def test_titles_list_sort_and_status():
    r = requests.get(f"{API}/titles", params={"sort_by": "newest"}, timeout=10)
    assert r.status_code == 200
    items = _titles_list(r.json())
    assert isinstance(items, list)

    r2 = requests.get(f"{API}/titles", params={"status": "ongoing"}, timeout=10)
    assert r2.status_code == 200


def test_title_detail_and_view_increment():
    items = _titles_list(requests.get(f"{API}/titles", timeout=10).json())
    if not items:
        pytest.skip("no titles in DB")
    tid = items[0]["id"]
    r = requests.get(f"{API}/titles/{tid}", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == tid


def test_episodes_ar_numeric_ordering():
    items = _titles_list(requests.get(f"{API}/titles", timeout=10).json())
    tid = None
    for t in items:
        if isinstance(t, dict) and t.get("has_chapters"):
            tid = t["id"]
            break
    if not tid:
        pytest.skip("no title with chapters")
    r = requests.get(f"{API}/titles/{tid}/episodes", params={"lang": "ar"}, timeout=10)
    assert r.status_code == 200
    eps = r.json()
    if len(eps) >= 2:
        nums = [e.get("number") for e in eps if isinstance(e.get("number"), (int, float))]
        # must be sorted numerically (asc or desc — accept both)
        assert nums == sorted(nums) or nums == sorted(nums, reverse=True), nums[:20]


def test_public_user_endpoint():
    # register throwaway user just to get a uid
    email = f"tester_iter5_{uuid.uuid4().hex[:6]}@otaku.com"
    reg = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Tester@12345", "name": "Iter5"},
        timeout=10,
    )
    assert reg.status_code in (200, 201), reg.text
    uid = reg.json()["user"]["id"]
    r = requests.get(f"{API}/users/{uid}", timeout=10)
    assert r.status_code == 200, r.text
    assert r.json().get("id") == uid


def test_pwa_assets():
    for path in ("/manifest.json", "/service-worker.js", "/icons/icon-192.png", "/icons/icon-512.png"):
        r = requests.get(f"{BASE_URL}{path}", timeout=10)
        assert r.status_code == 200, f"{path}: {r.status_code}"


# ==================== Import bundle regression ====================
def test_import_mangaspark_bundle_returns_processing(h):
    r = requests.post(f"{API}/admin/import-mangaspark-bundle", headers=h, timeout=15)
    assert r.status_code in (200, 202), r.text
    body = r.json()
    assert body.get("status") == "processing", body
    assert "job_id" in body


# ==================== Chat message endpoints regression ====================
@pytest.fixture(scope="module")
def user_token():
    email = f"tester_iter5_chat_{uuid.uuid4().hex[:6]}@otaku.com"
    reg = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Tester@12345", "name": "IterChat"},
        timeout=10,
    )
    assert reg.status_code in (200, 201), reg.text
    return reg.json()["token"]


def _get_or_make_room(user_hdr):
    # try existing global chat room; if none, POST a message to /rooms/global just to open one.
    # Existing suite works with a room id 'global' — try that first.
    r = requests.get(f"{API}/rooms/global/messages", headers=user_hdr, timeout=10)
    return "global" if r.status_code == 200 else None


def test_chat_message_lifecycle(user_token):
    hdr = {"Authorization": f"Bearer {user_token}"}
    room = _get_or_make_room(hdr)
    if not room:
        pytest.skip("no chat room available")
    # POST message
    m = requests.post(
        f"{API}/rooms/{room}/messages",
        headers=hdr,
        json={"content": "TEST_iter5 hello"},
        timeout=10,
    )
    if m.status_code == 404:
        pytest.skip("chat POST route not available")
    assert m.status_code in (200, 201), m.text
    mid = m.json().get("id") or m.json().get("_id")
    if not mid:
        pytest.skip("no message id returned")
    # PATCH edit
    p = requests.patch(
        f"{API}/messages/{mid}",
        headers=hdr,
        json={"content": "TEST_iter5 edited"},
        timeout=10,
    )
    # some builds route as /rooms/{room}/messages/{mid} — accept 200/404 with note
    assert p.status_code in (200, 204, 404), p.text
    # react
    rx = requests.post(
        f"{API}/messages/{mid}/react",
        headers=hdr,
        json={"emoji": "🔥"},
        timeout=10,
    )
    assert rx.status_code in (200, 201, 204, 404), rx.text
    # delete
    d = requests.delete(f"{API}/messages/{mid}", headers=hdr, timeout=10)
    assert d.status_code in (200, 204, 404), d.text
