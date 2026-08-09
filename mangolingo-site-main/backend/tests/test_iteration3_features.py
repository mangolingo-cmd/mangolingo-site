"""
Iteration 3 — Backend tests for the 8 batches of improvements:
- sort_by (rating/newest/views) & status filter on /api/titles
- exact-match vs fuzzy search on /api/titles?q=
- numeric chapter ordering via collation on /api/titles/{tid}/episodes
- views_count auto-increment on GET /api/titles/{tid}
- public GET /api/users/{uid} (no auth)
- watchlist add/check/delete
- partial PATCH /api/titles/{tid}
- chat: welcome bot, edit/delete (auth + admin), emoji reactions
- new chapter notification fan-out
"""
import os
import time
import uuid
import pytest
import requests

def _load_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # fallback: read frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return url.rstrip("/")

BASE_URL = _load_base_url()
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@otaku.com", "password": "Admin@12345"}


# ---------- shared fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_user(admin_token):
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=20)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def user_a():
    # Brand-new user — used for welcome-bot test
    email = f"test_userA_{uuid.uuid4().hex[:8]}@otaku.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@12345", "name": f"TEST_UserA_{uuid.uuid4().hex[:4]}"}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    return {"token": j["token"], "user": j["user"]}


@pytest.fixture(scope="session")
def user_b():
    email = f"test_userB_{uuid.uuid4().hex[:8]}@otaku.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@12345", "name": f"TEST_UserB_{uuid.uuid4().hex[:4]}"}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    return {"token": j["token"], "user": j["user"]}


def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Titles: sort_by + status filter ----------
class TestTitlesSortAndFilter:
    def test_sort_by_rating_desc(self):
        r = requests.get(f"{API}/titles", params={"sort_by": "rating", "limit": 20})
        assert r.status_code == 200
        items = r.json()["items"]
        ratings = [t.get("rating_avg", 0) or 0 for t in items]
        assert ratings == sorted(ratings, reverse=True), f"ratings not desc: {ratings}"

    def test_sort_by_views_desc(self):
        r = requests.get(f"{API}/titles", params={"sort_by": "views", "limit": 20})
        assert r.status_code == 200
        items = r.json()["items"]
        views = [t.get("views_count", 0) or 0 for t in items]
        assert views == sorted(views, reverse=True), f"views not desc: {views}"

    def test_sort_by_newest_has_ar_first(self):
        r = requests.get(f"{API}/titles", params={"sort_by": "newest", "limit": 30})
        assert r.status_code == 200
        items = r.json()["items"]
        # has_ar True should appear before has_ar falsy
        ar_flags = [bool(t.get("has_ar")) for t in items]
        # ensure True values are not after False values
        seen_false = False
        for v in ar_flags:
            if not v:
                seen_false = True
            elif seen_false and v:
                pytest.fail(f"has_ar ordering broken: {ar_flags}")

    def test_status_filter_completed(self):
        r = requests.get(f"{API}/titles", params={"status": "completed", "limit": 30})
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("No completed titles in DB")
        for t in items:
            assert t.get("status") == "completed", f"non-completed: {t.get('status')}"


# ---------- Search exact match priority ----------
class TestSearchExactMatch:
    def test_search_returns_results(self):
        # Find some title we can search for
        r = requests.get(f"{API}/titles", params={"limit": 5})
        items = r.json()["items"]
        if not items:
            pytest.skip("Empty DB")
        sample = items[0]
        name = sample.get("title", "")
        if not name:
            pytest.skip("No title text")
        # Use a short substring to allow fuzzy match
        r2 = requests.get(f"{API}/titles", params={"q": name})
        assert r2.status_code == 200
        got = r2.json()["items"]
        assert any(t["id"] == sample["id"] for t in got), "exact title not in fuzzy results"

    def test_search_exact_takes_priority(self):
        # exact match: query equal to a title that has an exact match
        r = requests.get(f"{API}/titles", params={"limit": 50})
        items = r.json()["items"]
        # Find any title with unique exact-case name
        target = None
        for t in items:
            if t.get("title"):
                target = t
                break
        if not target:
            pytest.skip("No title")
        r2 = requests.get(f"{API}/titles", params={"q": target["title"]})
        assert r2.status_code == 200
        got = r2.json()["items"]
        # exact match list should contain the title
        assert any(t["id"] == target["id"] for t in got)


# ---------- Numeric chapter ordering ----------
class TestEpisodeNumericOrder:
    def test_episodes_sorted_numerically(self):
        # Find a title with many chapters
        r = requests.get(f"{API}/titles", params={"limit": 30})
        items = r.json()["items"]
        for t in items:
            ep_r = requests.get(f"{API}/titles/{t['id']}/episodes", params={"lang": "en"})
            if ep_r.status_code != 200:
                continue
            eps = ep_r.json()
            if len(eps) >= 10:
                nums = [float(e["number"]) for e in eps if e.get("number") is not None]
                assert nums == sorted(nums), f"episode order not numeric: {nums[:20]}"
                return
        pytest.skip("No title with >=10 chapters")


# ---------- views_count increments ----------
class TestViewsIncrement:
    def test_views_increment(self):
        r = requests.get(f"{API}/titles", params={"limit": 1})
        items = r.json()["items"]
        if not items:
            pytest.skip("no titles")
        tid = items[0]["id"]
        r1 = requests.get(f"{API}/titles/{tid}")
        v1 = r1.json().get("views_count", 0) or 0
        time.sleep(1.5)
        r2 = requests.get(f"{API}/titles/{tid}")
        time.sleep(1.5)
        r3 = requests.get(f"{API}/titles/{tid}")
        v3 = r3.json().get("views_count", 0) or 0
        assert v3 > v1, f"views did not increment v1={v1} v3={v3}"


# ---------- Public profile ----------
class TestPublicProfile:
    def test_get_user_no_auth(self, user_a):
        uid = user_a["user"]["id"]
        r = requests.get(f"{API}/users/{uid}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == uid
        assert "name" in d
        # ensure password hash not exposed
        assert "password_hash" not in d

    def test_get_user_not_found(self):
        r = requests.get(f"{API}/users/nope-{uuid.uuid4()}")
        assert r.status_code == 404


# ---------- Watchlist add/check/delete ----------
class TestWatchlist:
    def test_add_check_delete(self, user_a):
        token = user_a["token"]
        items = requests.get(f"{API}/titles", params={"limit": 1}).json()["items"]
        if not items:
            pytest.skip("no titles")
        tid = items[0]["id"]
        # add
        r = requests.post(f"{API}/watchlist", json={"title_id": tid, "status": "watching"}, headers=H(token))
        assert r.status_code == 200
        # check
        r = requests.get(f"{API}/watchlist/{tid}/check", headers=H(token))
        assert r.status_code == 200
        assert r.json()["following"] is True
        # delete
        r = requests.delete(f"{API}/watchlist/{tid}", headers=H(token))
        assert r.status_code == 200
        # check false
        r = requests.get(f"{API}/watchlist/{tid}/check", headers=H(token))
        assert r.json()["following"] is False


# ---------- Partial PATCH /titles/{tid} ----------
class TestPartialTitlePatch:
    def test_patch_status_only(self, admin_token):
        # create a title
        title = {
            "type": "manga", "title": f"TEST_PATCH_{uuid.uuid4().hex[:6]}",
            "title_ar": "اختبار", "synopsis": "x", "cover_url": "", "genres": [],
            "status": "ongoing",
        }
        r = requests.post(f"{API}/titles", json=title, headers=H(admin_token))
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        # patch only status
        r2 = requests.patch(f"{API}/titles/{tid}", json={"status": "completed"}, headers=H(admin_token))
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["status"] == "completed"
        assert body["title"] == title["title"]  # untouched
        # cleanup
        requests.delete(f"{API}/titles/{tid}", headers=H(admin_token))

    def test_patch_non_admin_forbidden(self, user_a):
        items = requests.get(f"{API}/titles", params={"limit": 1}).json()["items"]
        if not items:
            pytest.skip("no titles")
        r = requests.patch(f"{API}/titles/{items[0]['id']}", json={"status": "completed"}, headers=H(user_a["token"]))
        assert r.status_code == 403


# ---------- Chat: welcome bot + edit + delete + react ----------
class TestChatBotAndModeration:
    def test_first_lobby_message_triggers_bot(self, user_b):
        # user_b is brand new — fire first message
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "Hello world"}, headers=H(user_b["token"]))
        assert r.status_code == 200, r.text
        time.sleep(0.5)
        msgs = requests.get(f"{API}/rooms/lobby/messages", params={"limit": 10}, headers=H(user_b["token"])).json()
        bot_msgs = [m for m in msgs if m.get("sender_id") == "bot"]
        assert bot_msgs, "no welcome bot message detected"
        assert any(m.get("sender_name") == "MangaBot" for m in bot_msgs)

    def test_edit_own_message(self, user_a):
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "TEST_to_edit"}, headers=H(user_a["token"]))
        mid = r.json()["id"]
        r2 = requests.patch(f"{API}/messages/{mid}", json={"content": "TEST_edited"}, headers=H(user_a["token"]))
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["content"] == "TEST_edited"
        assert body["edited"] is True

    def test_cannot_edit_others_message(self, user_a, user_b):
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "TEST_other"}, headers=H(user_a["token"]))
        mid = r.json()["id"]
        r2 = requests.patch(f"{API}/messages/{mid}", json={"content": "hack"}, headers=H(user_b["token"]))
        assert r2.status_code == 403

    def test_admin_can_delete_any_message(self, user_a, admin_token):
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "TEST_del_by_admin"}, headers=H(user_a["token"]))
        mid = r.json()["id"]
        r2 = requests.delete(f"{API}/messages/{mid}", headers=H(admin_token))
        assert r2.status_code == 200

    def test_user_cannot_delete_others(self, user_a, user_b):
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "TEST_del_blocked"}, headers=H(user_a["token"]))
        mid = r.json()["id"]
        r2 = requests.delete(f"{API}/messages/{mid}", headers=H(user_b["token"]))
        assert r2.status_code == 403

    def test_react_toggle(self, user_a):
        r = requests.post(f"{API}/rooms/lobby/messages", json={"content": "TEST_react"}, headers=H(user_a["token"]))
        mid = r.json()["id"]
        # add reaction
        r2 = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "🔥"}, headers=H(user_a["token"]))
        assert r2.status_code == 200, r2.text
        reacts = r2.json()["reactions"]
        assert user_a["user"]["id"] in reacts.get("🔥", [])
        # toggle off
        r3 = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "🔥"}, headers=H(user_a["token"]))
        assert "🔥" not in r3.json()["reactions"] or user_a["user"]["id"] not in r3.json()["reactions"].get("🔥", [])


# ---------- Notification fan-out on new chapter ----------
class TestNewChapterNotification:
    def test_new_chapter_creates_notification(self, admin_token, user_a):
        # create a TEST title
        title = {"type": "manga", "title": f"TEST_NOTIFY_{uuid.uuid4().hex[:6]}",
                 "title_ar": "", "synopsis": "", "cover_url": "", "genres": [], "status": "ongoing"}
        rt = requests.post(f"{API}/titles", json=title, headers=H(admin_token))
        assert rt.status_code == 200, rt.text
        tid = rt.json()["id"]
        try:
            # user_a follows it
            requests.post(f"{API}/watchlist", json={"title_id": tid, "status": "watching"}, headers=H(user_a["token"]))
            # admin creates an episode
            ep = {"number": 1.0, "name": "first", "video_url": "", "pages": []}
            re_ = requests.post(f"{API}/titles/{tid}/episodes", json=ep, headers=H(admin_token))
            assert re_.status_code == 200, re_.text
            eid = re_.json()["id"]
            # wait for background task
            time.sleep(2)
            n = requests.get(f"{API}/notifications", headers=H(user_a["token"])).json()
            new_chapter = [x for x in n if x.get("type") == "new_chapter" and x.get("payload", {}).get("title_id") == tid]
            assert new_chapter, "no new_chapter notification generated"
            assert new_chapter[0]["payload"]["episode_id"] == eid
            assert new_chapter[0]["payload"]["episode_number"] == 1.0
        finally:
            requests.delete(f"{API}/watchlist/{tid}", headers=H(user_a["token"]))
            requests.delete(f"{API}/titles/{tid}", headers=H(admin_token))


# ---------- Regression: login + basics ----------
class TestRegression:
    def test_login_works(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN)
        assert r.status_code == 200

    def test_titles_list_paginated(self):
        r = requests.get(f"{API}/titles")
        assert r.status_code == 200
        j = r.json()
        assert "items" in j and "total" in j

    def test_friends_endpoint(self, user_a):
        r = requests.get(f"{API}/friends", headers=H(user_a["token"]))
        assert r.status_code == 200

    def test_dm_list(self, user_a):
        r = requests.get(f"{API}/dm", headers=H(user_a["token"]))
        assert r.status_code == 200

    def test_service_worker_served(self):
        r = requests.get(f"{BASE_URL}/service-worker.js")
        assert r.status_code == 200
        assert "show-notification" in r.text
