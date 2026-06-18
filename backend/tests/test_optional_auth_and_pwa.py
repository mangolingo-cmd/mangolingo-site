"""Tests for optional-auth (guest) endpoints, Continue Reading, and PWA assets."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@otaku.com", "password": "Admin@12345"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def tester():
    email = f"tester_{uuid.uuid4().hex[:6]}@otaku.com"
    payload = {"email": email, "password": "Tester@12345", "name": "Tester"}
    r = requests.post(f"{API}/auth/register", json=payload)
    assert r.status_code == 200, r.text
    return {"token": r.json()["token"], "id": r.json()["user"]["id"], "email": email}


def _extract_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return []


@pytest.fixture(scope="module")
def sample_title():
    r = requests.get(f"{API}/titles")
    assert r.status_code == 200
    items = _extract_items(r.json())
    assert len(items) >= 1
    return items[0]


@pytest.fixture(scope="module")
def sample_episode(sample_title):
    """Find or seed an episode for the sample title."""
    tid = sample_title["id"]
    r = requests.get(f"{API}/titles/{tid}/episodes")
    items = r.json() if r.status_code == 200 else []
    if items:
        return items[0]
    # No episodes - seed one as admin
    r2 = requests.post(f"{API}/auth/login", json=ADMIN)
    tok = r2.json()["token"]
    ep = {"number": 1.0, "name": "TEST_ep1", "pages": ["https://example.com/p1.jpg"]}
    r3 = requests.post(f"{API}/titles/{tid}/episodes", json=ep,
                       headers={"Authorization": f"Bearer {tok}"})
    assert r3.status_code == 200, r3.text
    return r3.json()


# ---- Public (guest) endpoints ----
class TestPublicAccess:
    def test_titles_list_no_auth(self):
        r = requests.get(f"{API}/titles")
        assert r.status_code == 200
        items = _extract_items(r.json())
        assert isinstance(items, list)
        assert len(items) >= 1

    def test_title_detail_no_auth(self, sample_title):
        r = requests.get(f"{API}/titles/{sample_title['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == sample_title["id"]

    def test_episodes_list_no_auth(self, sample_title):
        r = requests.get(f"{API}/titles/{sample_title['id']}/episodes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_single_episode_no_auth(self, sample_title, sample_episode):
        r = requests.get(f"{API}/titles/{sample_title['id']}/episodes/{sample_episode['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == sample_episode["id"]

    def test_episode_pages_no_auth(self, sample_episode):
        # Strictly no Authorization header
        r = requests.get(f"{API}/episodes/{sample_episode['id']}/pages")
        # Should be either 200 (data) or 502 (upstream CDN problem - known)
        assert r.status_code in (200, 502), f"Got {r.status_code}: {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert "pages" in data
            assert isinstance(data["pages"], list)

    def test_reviews_list_no_auth(self, sample_title):
        r = requests.get(f"{API}/titles/{sample_title['id']}/reviews")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---- Social endpoints must require auth ----
class TestSocialRequireAuth:
    def test_post_review_no_auth(self, sample_title):
        r = requests.post(f"{API}/titles/{sample_title['id']}/reviews",
                          json={"rating": 8, "content": "guest attempt"})
        assert r.status_code in (401, 403)

    def test_post_message_no_auth(self):
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "hi"})
        assert r.status_code in (401, 403)

    def test_watchlist_no_auth(self):
        r = requests.get(f"{API}/watchlist")
        assert r.status_code in (401, 403)

    def test_friends_no_auth(self):
        r = requests.get(f"{API}/friends")
        assert r.status_code in (401, 403)


# ---- Continue Reading ----
class TestContinueReading:
    def test_save_progress_requires_auth(self, sample_title, sample_episode):
        r = requests.post(f"{API}/reading/progress", json={
            "title_id": sample_title["id"],
            "episode_id": sample_episode["id"],
            "episode_number": 1,
        })
        assert r.status_code in (401, 403)

    def test_save_progress_authenticated(self, tester, sample_title, sample_episode):
        r = requests.post(f"{API}/reading/progress",
                          headers={"Authorization": f"Bearer {tester['token']}"},
                          json={
                              "title_id": sample_title["id"],
                              "episode_id": sample_episode["id"],
                              "episode_number": sample_episode.get("number", 1),
                              "page": 0,
                          })
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_get_progress_for_title(self, tester, sample_title, sample_episode):
        r = requests.get(f"{API}/reading/progress/{sample_title['id']}",
                         headers={"Authorization": f"Bearer {tester['token']}"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("episode_id") == sample_episode["id"]
        assert data.get("title_id") == sample_title["id"]

    def test_continue_list(self, tester, sample_title):
        r = requests.get(f"{API}/reading/continue",
                         headers={"Authorization": f"Bearer {tester['token']}"})
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        found = next((x for x in items if x["title_id"] == sample_title["id"]), None)
        assert found is not None
        # Title doc is enriched
        assert "title" in found
        assert found["title"]["id"] == sample_title["id"]

    def test_continue_list_unauth(self):
        r = requests.get(f"{API}/reading/continue")
        assert r.status_code in (401, 403)


# ---- PWA static assets ----
class TestPWAAssets:
    def test_manifest(self):
        r = requests.get(f"{BASE_URL}/manifest.json")
        assert r.status_code == 200, r.status_code
        data = r.json()
        assert data.get("name")
        assert data.get("short_name")
        assert data.get("start_url") == "/"
        assert data.get("display") == "standalone"
        icons = data.get("icons") or []
        sizes = {i.get("sizes") for i in icons}
        assert "192x192" in sizes
        assert "512x512" in sizes

    def test_service_worker(self):
        r = requests.get(f"{BASE_URL}/service-worker.js")
        assert r.status_code == 200
        ctype = r.headers.get("content-type", "")
        assert "javascript" in ctype or "text" in ctype

    def test_icon_192(self):
        r = requests.get(f"{BASE_URL}/icons/icon-192.png")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")

    def test_icon_512(self):
        r = requests.get(f"{BASE_URL}/icons/icon-512.png")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")


# ---- Legal pages (served by frontend SPA -> 200 HTML) ----
class TestLegalPages:
    def test_privacy_route(self):
        r = requests.get(f"{BASE_URL}/privacy")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()

    def test_terms_route(self):
        r = requests.get(f"{BASE_URL}/terms")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower()
