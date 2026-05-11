"""Backend API tests for Otaku Hub."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback: read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@otaku.com", "password": "Admin@12345"}
TESTER_EMAIL = f"tester_{uuid.uuid4().hex[:6]}@otaku.com"
TESTER = {"email": TESTER_EMAIL, "password": "Tester@12345", "name": "Tester"}
TESTER2_EMAIL = f"tester2_{uuid.uuid4().hex[:6]}@otaku.com"
TESTER2 = {"email": TESTER2_EMAIL, "password": "Tester@12345", "name": "Tester2"}

state = {}


def h(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Auth ----
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_register_tester():
    r = requests.post(f"{API}/auth/register", json=TESTER)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and "user" in data
    assert data["user"]["email"] == TESTER["email"]
    assert data["user"]["role"] == "user"
    state["tester_token"] = data["token"]
    state["tester_id"] = data["user"]["id"]


def test_register_tester2():
    r = requests.post(f"{API}/auth/register", json=TESTER2)
    assert r.status_code == 200
    state["tester2_token"] = r.json()["token"]
    state["tester2_id"] = r.json()["user"]["id"]


def test_register_duplicate():
    r = requests.post(f"{API}/auth/register", json=TESTER)
    assert r.status_code == 400


def test_login_admin():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["role"] == "admin"
    state["admin_token"] = data["token"]
    state["admin_id"] = data["user"]["id"]


def test_login_wrong():
    r = requests.post(f"{API}/auth/login", json={"email": TESTER["email"], "password": "wrong"})
    assert r.status_code == 401


def test_me_with_token():
    r = requests.get(f"{API}/auth/me", headers=h(state["tester_token"]))
    assert r.status_code == 200
    assert r.json()["email"] == TESTER["email"]


def test_me_no_token():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_patch_me():
    r = requests.patch(f"{API}/auth/me", headers=h(state["tester_token"]), json={"bio": "hello bio"})
    assert r.status_code == 200
    assert r.json()["bio"] == "hello bio"
    # verify persisted
    r2 = requests.get(f"{API}/auth/me", headers=h(state["tester_token"]))
    assert r2.json()["bio"] == "hello bio"


# ---- Titles ----
def test_list_titles_seeded():
    r = requests.get(f"{API}/titles")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 6
    state["sample_title_id"] = items[0]["id"]


def test_filter_type_anime():
    r = requests.get(f"{API}/titles", params={"type": "anime"})
    assert r.status_code == 200
    items = r.json()
    assert all(t["type"] == "anime" for t in items)
    assert len(items) >= 2


def test_search_arabic():
    r = requests.get(f"{API}/titles", params={"q": "ون"})
    assert r.status_code == 200
    items = r.json()
    assert any("ون" in (t.get("title_ar") or "") for t in items)


def test_get_title_by_id():
    r = requests.get(f"{API}/titles/{state['sample_title_id']}")
    assert r.status_code == 200
    assert r.json()["id"] == state["sample_title_id"]


def test_get_title_404():
    r = requests.get(f"{API}/titles/nonexistent")
    assert r.status_code == 404


def test_create_title_forbidden_for_user():
    payload = {"type": "anime", "title": "TEST_ShouldFail", "title_ar": "اختبار"}
    r = requests.post(f"{API}/titles", headers=h(state["tester_token"]), json=payload)
    assert r.status_code == 403


def test_create_title_admin():
    payload = {
        "type": "anime",
        "title": "TEST_AdminTitle",
        "title_ar": "اختبار العنوان",
        "synopsis": "test",
        "cover_url": "https://example.com/c.jpg",
        "genres": ["أكشن"],
        "status": "ongoing",
        "year": 2024,
    }
    r = requests.post(f"{API}/titles", headers=h(state["admin_token"]), json=payload)
    assert r.status_code == 200, r.text
    state["new_title_id"] = r.json()["id"]
    # verify GET
    r2 = requests.get(f"{API}/titles/{state['new_title_id']}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "TEST_AdminTitle"


# ---- Reviews ----
def test_post_review_and_avg():
    payload = {"rating": 8, "content": "ممتاز!"}
    r = requests.post(f"{API}/titles/{state['new_title_id']}/reviews", headers=h(state["tester_token"]), json=payload)
    assert r.status_code == 200
    assert r.json()["rating"] == 8
    # verify list
    r2 = requests.get(f"{API}/titles/{state['new_title_id']}/reviews")
    assert r2.status_code == 200
    assert len(r2.json()) >= 1
    # verify avg update
    r3 = requests.get(f"{API}/titles/{state['new_title_id']}")
    assert r3.json()["rating_avg"] == 8.0
    assert r3.json()["rating_count"] == 1


# ---- Watchlist ----
def test_watchlist_upsert_and_list():
    r = requests.post(f"{API}/watchlist", headers=h(state["tester_token"]), json={"title_id": state["new_title_id"], "status": "watching"})
    assert r.status_code == 200
    r2 = requests.get(f"{API}/watchlist", headers=h(state["tester_token"]))
    assert r2.status_code == 200
    items = r2.json()
    assert any(e["title_id"] == state["new_title_id"] and e["status"] == "watching" for e in items)
    # update
    r3 = requests.post(f"{API}/watchlist", headers=h(state["tester_token"]), json={"title_id": state["new_title_id"], "status": "completed"})
    assert r3.status_code == 200
    r4 = requests.get(f"{API}/watchlist", headers=h(state["tester_token"]))
    assert any(e["title_id"] == state["new_title_id"] and e["status"] == "completed" for e in r4.json())


# ---- Users / Friends ----
def test_user_search():
    r = requests.get(f"{API}/users/search", headers=h(state["tester_token"]), params={"q": "Tester2"})
    assert r.status_code == 200
    found = r.json()
    assert any(u["id"] == state["tester2_id"] for u in found)


def test_friend_request_and_accept():
    r = requests.post(f"{API}/friends/request/{state['tester2_id']}", headers=h(state["tester_token"]))
    assert r.status_code == 200
    # duplicate
    r_dup = requests.post(f"{API}/friends/request/{state['tester2_id']}", headers=h(state["tester_token"]))
    assert r_dup.status_code == 400
    # incoming for tester2
    rf = requests.get(f"{API}/friends", headers=h(state["tester2_token"]))
    assert rf.status_code == 200
    assert any(u["id"] == state["tester_id"] for u in rf.json()["incoming"])
    # accept
    r2 = requests.post(f"{API}/friends/respond/{state['tester_id']}", headers=h(state["tester2_token"]), params={"accept": "true"})
    assert r2.status_code == 200
    rf2 = requests.get(f"{API}/friends", headers=h(state["tester_token"]))
    assert any(u["id"] == state["tester2_id"] for u in rf2.json()["friends"])


# ---- Messages ----
def test_lobby_post_get():
    r = requests.post(f"{API}/rooms/lobby/messages", headers=h(state["tester_token"]), json={"content": "مرحبا"})
    assert r.status_code == 200
    r2 = requests.get(f"{API}/rooms/lobby/messages", headers=h(state["tester_token"]))
    assert r2.status_code == 200
    assert any(m["content"] == "مرحبا" for m in r2.json())


def test_title_room_post():
    r = requests.post(f"{API}/rooms/{state['new_title_id']}/messages", headers=h(state["tester_token"]), json={"content": "نقاش"})
    assert r.status_code == 200


def test_title_room_404():
    r = requests.post(f"{API}/rooms/bogus_title_id/messages", headers=h(state["tester_token"]), json={"content": "x"})
    assert r.status_code == 404


# ---- DM ----
def test_dm_flow_and_403():
    r = requests.get(f"{API}/dm/{state['tester2_id']}/room", headers=h(state["tester_token"]))
    assert r.status_code == 200
    state["dm_room"] = r.json()["room_id"]
    assert state["dm_room"].startswith("dm_")
    # post message
    rp = requests.post(f"{API}/rooms/{state['dm_room']}/messages", headers=h(state["tester_token"]), json={"content": "hi dm"})
    assert rp.status_code == 200
    # get
    rg = requests.get(f"{API}/rooms/{state['dm_room']}/messages", headers=h(state["tester2_token"]))
    assert rg.status_code == 200
    assert any(m["content"] == "hi dm" for m in rg.json())
    # admin (non-participant) -> 403
    r403 = requests.get(f"{API}/rooms/{state['dm_room']}/messages", headers=h(state["admin_token"]))
    assert r403.status_code == 403
    r403p = requests.post(f"{API}/rooms/{state['dm_room']}/messages", headers=h(state["admin_token"]), json={"content": "x"})
    assert r403p.status_code == 403


# ---- Notifications ----
def test_notifications():
    # tester2 should have friend_request + dm notifications
    r = requests.get(f"{API}/notifications", headers=h(state["tester2_token"]))
    assert r.status_code == 200
    types = {n["type"] for n in r.json()}
    assert "friend_request" in types
    assert "dm" in types
    rc = requests.get(f"{API}/notifications/unread_count", headers=h(state["tester2_token"]))
    assert rc.status_code == 200
    assert rc.json()["count"] >= 1
    rr = requests.post(f"{API}/notifications/read_all", headers=h(state["tester2_token"]))
    assert rr.status_code == 200
    rc2 = requests.get(f"{API}/notifications/unread_count", headers=h(state["tester2_token"]))
    assert rc2.json()["count"] == 0


# ---- Cleanup (admin delete title) ----
def test_delete_title_user_forbidden():
    r = requests.delete(f"{API}/titles/{state['new_title_id']}", headers=h(state["tester_token"]))
    assert r.status_code == 403


def test_delete_title_admin():
    r = requests.delete(f"{API}/titles/{state['new_title_id']}", headers=h(state["admin_token"]))
    assert r.status_code == 200
    r2 = requests.get(f"{API}/titles/{state['new_title_id']}")
    assert r2.status_code == 404
