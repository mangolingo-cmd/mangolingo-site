from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import bcrypt
import jwt
import httpx
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

# -------- Config --------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-dev-secret-please")
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@otaku.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Otaku Hub API")
api = APIRouter(prefix="/api")

# -------- Models --------
class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar: Optional[str] = None
    bio: Optional[str] = None
    role: str = "user"

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=40)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TitleIn(BaseModel):
    type: str  # anime | manhwa | manga
    title: str
    title_ar: Optional[str] = ""
    synopsis: str = ""
    cover_url: str = ""
    banner_url: Optional[str] = ""
    genres: List[str] = []
    status: str = "ongoing"
    episodes: Optional[int] = None
    chapters: Optional[int] = None
    year: Optional[int] = None

class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=10)
    content: str = Field(min_length=1, max_length=2000)

class WatchlistIn(BaseModel):
    title_id: str
    status: str  # watching | completed | plan | dropped | favorite

class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None

# -------- Helpers --------
def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False

def make_token(uid: str, email: str) -> str:
    payload = {
        "sub": uid,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u["name"],
        "avatar": u.get("avatar") or "",
        "bio": u.get("bio") or "",
        "role": u.get("role", "user"),
    }

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = None
    if auth.startswith("Bearer "):
        token = auth[7:]
    elif request.cookies.get("access_token"):
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user

def dm_room_id(a: str, b: str) -> str:
    return "dm_" + "_".join(sorted([a, b]))

# -------- Auth endpoints --------
@api.post("/auth/register")
async def register(data: RegisterIn):
    email = data.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "البريد الإلكتروني مستخدم بالفعل")
    uid = str(uuid.uuid4())
    doc = {
        "id": uid,
        "email": email,
        "password_hash": hash_pw(data.password),
        "name": data.name,
        "avatar": "",
        "bio": "",
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = make_token(uid, email)
    return {"token": token, "user": public_user(doc)}

@api.post("/auth/login")
async def login(data: LoginIn):
    email = data.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_pw(data.password, user["password_hash"]):
        raise HTTPException(401, "بيانات الدخول غير صحيحة")
    token = make_token(user["id"], email)
    return {"token": token, "user": public_user(user)}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)

@api.patch("/auth/me")
async def update_me(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return public_user(fresh)

# -------- Titles --------
@api.get("/titles")
async def list_titles(type: Optional[str] = None, q: Optional[str] = None, limit: int = 60):
    query = {}
    if type:
        query["type"] = type
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"title_ar": {"$regex": q, "$options": "i"}},
        ]
    items = await db.titles.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return items

@api.get("/titles/{tid}")
async def get_title(tid: str):
    t = await db.titles.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "العنوان غير موجود")
    return t

@api.post("/titles")
async def create_title(data: TitleIn, _: dict = Depends(require_admin)):
    if data.type not in ("manhwa", "manga"):
        raise HTTPException(400, "نوع غير صالح — manga أو manhwa فقط")
    tid = str(uuid.uuid4())
    doc = data.model_dump()
    doc.update({
        "id": tid,
        "rating_avg": 0,
        "rating_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.titles.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/titles/{tid}")
async def update_title(tid: str, data: TitleIn, _: dict = Depends(require_admin)):
    res = await db.titles.update_one({"id": tid}, {"$set": data.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "العنوان غير موجود")
    return await db.titles.find_one({"id": tid}, {"_id": 0})

@api.delete("/titles/{tid}")
async def delete_title(tid: str, _: dict = Depends(require_admin)):
    await db.titles.delete_one({"id": tid})
    return {"ok": True}

# -------- Reviews --------
@api.get("/titles/{tid}/reviews")
async def list_reviews(tid: str):
    items = await db.reviews.find({"title_id": tid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items

@api.post("/titles/{tid}/reviews")
async def add_review(tid: str, data: ReviewIn, user: dict = Depends(get_current_user)):
    title = await db.titles.find_one({"id": tid})
    if not title:
        raise HTTPException(404, "العنوان غير موجود")
    rid = str(uuid.uuid4())
    doc = {
        "id": rid,
        "title_id": tid,
        "user_id": user["id"],
        "user_name": user["name"],
        "user_avatar": user.get("avatar") or "",
        "rating": data.rating,
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.reviews.insert_one(doc)
    # update average
    cursor = db.reviews.find({"title_id": tid}, {"_id": 0, "rating": 1})
    ratings = [r["rating"] async for r in cursor]
    if ratings:
        avg = sum(ratings) / len(ratings)
        await db.titles.update_one({"id": tid}, {"$set": {"rating_avg": round(avg, 1), "rating_count": len(ratings)}})
    doc.pop("_id", None)
    return doc

# -------- Watchlist --------
@api.get("/watchlist")
async def my_watchlist(user: dict = Depends(get_current_user)):
    entries = await db.watchlist.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    # join with titles
    title_ids = [e["title_id"] for e in entries]
    titles = await db.titles.find({"id": {"$in": title_ids}}, {"_id": 0}).to_list(500)
    tmap = {t["id"]: t for t in titles}
    return [{**e, "title": tmap.get(e["title_id"])} for e in entries]

@api.post("/watchlist")
async def set_watchlist(data: WatchlistIn, user: dict = Depends(get_current_user)):
    if data.status not in ("watching", "completed", "plan", "dropped", "favorite"):
        raise HTTPException(400, "حالة غير صالحة")
    await db.watchlist.update_one(
        {"user_id": user["id"], "title_id": data.title_id},
        {"$set": {
            "user_id": user["id"],
            "title_id": data.title_id,
            "status": data.status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True}

@api.delete("/watchlist/{title_id}")
async def remove_watchlist(title_id: str, user: dict = Depends(get_current_user)):
    await db.watchlist.delete_one({"user_id": user["id"], "title_id": title_id})
    return {"ok": True}

# -------- Users / Friends --------
@api.get("/users/search")
async def search_users(q: str, user: dict = Depends(get_current_user)):
    if not q.strip():
        return []
    users = await db.users.find(
        {"name": {"$regex": q, "$options": "i"}, "id": {"$ne": user["id"]}},
        {"_id": 0, "password_hash": 0},
    ).to_list(20)
    return [public_user(u) for u in users]

@api.get("/users/{uid}")
async def get_user(uid: str):
    u = await db.users.find_one({"id": uid}, {"_id": 0})
    if not u:
        raise HTTPException(404, "المستخدم غير موجود")
    return public_user(u)

@api.get("/friends")
async def list_friends(user: dict = Depends(get_current_user)):
    edges = await db.friendships.find({
        "$or": [{"requester_id": user["id"]}, {"addressee_id": user["id"]}],
    }, {"_id": 0}).to_list(500)
    # collect friend ids
    accepted, incoming, outgoing = [], [], []
    for e in edges:
        other_id = e["addressee_id"] if e["requester_id"] == user["id"] else e["requester_id"]
        if e["status"] == "accepted":
            accepted.append(other_id)
        elif e["status"] == "pending":
            if e["addressee_id"] == user["id"]:
                incoming.append(other_id)
            else:
                outgoing.append(other_id)
    all_ids = list(set(accepted + incoming + outgoing))
    users = await db.users.find({"id": {"$in": all_ids}}, {"_id": 0}).to_list(500)
    umap = {u["id"]: public_user(u) for u in users}
    return {
        "friends": [umap[i] for i in accepted if i in umap],
        "incoming": [umap[i] for i in incoming if i in umap],
        "outgoing": [umap[i] for i in outgoing if i in umap],
    }

@api.post("/friends/request/{uid}")
async def request_friend(uid: str, user: dict = Depends(get_current_user)):
    if uid == user["id"]:
        raise HTTPException(400, "لا يمكنك إضافة نفسك")
    target = await db.users.find_one({"id": uid})
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    existing = await db.friendships.find_one({
        "$or": [
            {"requester_id": user["id"], "addressee_id": uid},
            {"requester_id": uid, "addressee_id": user["id"]},
        ]
    })
    if existing:
        raise HTTPException(400, "طلب الصداقة موجود مسبقاً")
    fid = str(uuid.uuid4())
    await db.friendships.insert_one({
        "id": fid,
        "requester_id": user["id"],
        "addressee_id": uid,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "type": "friend_request",
        "payload": {"from_id": user["id"], "from_name": user["name"]},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}

@api.post("/friends/respond/{uid}")
async def respond_friend(uid: str, accept: bool = True, user: dict = Depends(get_current_user)):
    edge = await db.friendships.find_one({
        "requester_id": uid,
        "addressee_id": user["id"],
        "status": "pending",
    })
    if not edge:
        raise HTTPException(404, "الطلب غير موجود")
    if accept:
        await db.friendships.update_one({"id": edge["id"]}, {"$set": {"status": "accepted"}})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "type": "friend_accepted",
            "payload": {"from_id": user["id"], "from_name": user["name"]},
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await db.friendships.delete_one({"id": edge["id"]})
    return {"ok": True}

@api.delete("/friends/{uid}")
async def remove_friend(uid: str, user: dict = Depends(get_current_user)):
    await db.friendships.delete_one({
        "$or": [
            {"requester_id": user["id"], "addressee_id": uid},
            {"requester_id": uid, "addressee_id": user["id"]},
        ]
    })
    return {"ok": True}

# -------- Rooms / Messages --------
@api.get("/rooms/{room_id}/messages")
async def list_messages(room_id: str, limit: int = 100, user: dict = Depends(get_current_user)):
    # For DM rooms, ensure user is participant
    if room_id.startswith("dm_"):
        parts = room_id[3:].split("_")
        if user["id"] not in parts:
            raise HTTPException(403, "ليس لديك صلاحية")
    msgs = await db.messages.find({"room_id": room_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return list(reversed(msgs))

@api.post("/rooms/{room_id}/messages")
async def post_message(room_id: str, data: MessageIn, user: dict = Depends(get_current_user)):
    if room_id.startswith("dm_"):
        parts = room_id[3:].split("_")
        if user["id"] not in parts:
            raise HTTPException(403, "ليس لديك صلاحية")
        # notify the other participant
        other = [p for p in parts if p != user["id"]]
        if other:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": other[0],
                "type": "dm",
                "payload": {"from_id": user["id"], "from_name": user["name"], "preview": data.content[:80]},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    elif room_id != "lobby":
        # discussion room for a title — verify title exists
        title = await db.titles.find_one({"id": room_id})
        if not title:
            raise HTTPException(404, "الغرفة غير موجودة")

    msg = {
        "id": str(uuid.uuid4()),
        "room_id": room_id,
        "sender_id": user["id"],
        "sender_name": user["name"],
        "sender_avatar": user.get("avatar") or "",
        "content": data.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    return msg

# -------- DM helpers --------
@api.get("/dm/{uid}/room")
async def get_dm_room(uid: str, user: dict = Depends(get_current_user)):
    return {"room_id": dm_room_id(user["id"], uid)}

@api.get("/dm")
async def list_dms(user: dict = Depends(get_current_user)):
    # find all dm rooms involving user
    rooms = await db.messages.distinct("room_id", {"room_id": {"$regex": "^dm_"}})
    mine = [r for r in rooms if user["id"] in r[3:].split("_")]
    threads = []
    for r in mine:
        other_id = [p for p in r[3:].split("_") if p != user["id"]][0]
        other = await db.users.find_one({"id": other_id}, {"_id": 0})
        last = await db.messages.find_one({"room_id": r}, {"_id": 0}, sort=[("created_at", -1)])
        if other and last:
            threads.append({
                "room_id": r,
                "user": public_user(other),
                "last_message": last["content"],
                "last_at": last["created_at"],
            })
    threads.sort(key=lambda x: x["last_at"], reverse=True)
    return threads

# -------- Notifications --------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return items

@api.get("/notifications/unread_count")
async def unread_count(user: dict = Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"count": n}

@api.post("/notifications/read_all")
async def read_all(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True}

# -------- Episodes / Chapters --------
class EpisodeIn(BaseModel):
    number: float
    name: Optional[str] = ""
    video_url: Optional[str] = ""  # for anime
    pages: List[str] = []           # for manga/manhwa

@api.get("/titles/{tid}/episodes")
async def list_episodes(tid: str):
    title = await db.titles.find_one({"id": tid}, {"_id": 0})
    if not title:
        raise HTTPException(404, "العنوان غير موجود")
    items = await db.episodes.find({"title_id": tid}, {"_id": 0}).sort("number", 1).to_list(2000)
    # Lazy-load chapters from MangaDex if linked and not yet cached
    if not items and title.get("mangadex_id"):
        await _fetch_and_cache_mangadex_chapters(title)
        items = await db.episodes.find({"title_id": tid}, {"_id": 0}).sort("number", 1).to_list(2000)
    return items

@api.get("/episodes/{eid}/pages")
async def get_episode_pages(eid: str, user: dict = Depends(get_current_user)):
    """Return live page image URLs. For MangaDex chapters: fetched fresh from at-home server.
    For manually-added chapters: returns stored pages."""
    ep = await db.episodes.find_one({"id": eid}, {"_id": 0})
    if not ep:
        raise HTTPException(404, "الفصل غير موجود")
    if ep.get("mangadex_chapter_id"):
        try:
            async with httpx.AsyncClient(timeout=15) as h:
                r = await h.get(f"https://api.mangadex.org/at-home/server/{ep['mangadex_chapter_id']}")
                r.raise_for_status()
                d = r.json()
                base = d["baseUrl"]
                ch = d["chapter"]
                pages = [f"{base}/data/{ch['hash']}/{f}" for f in ch.get("data", [])]
                return {"pages": pages}
        except Exception as e:
            logger.exception("MangaDex pages fetch failed")
            raise HTTPException(502, "تعذر جلب الصفحات من المصدر")
    return {"pages": ep.get("pages", [])}

@api.get("/titles/{tid}/episodes/{eid}")
async def get_episode(tid: str, eid: str, user: dict = Depends(get_current_user)):
    ep = await db.episodes.find_one({"id": eid, "title_id": tid}, {"_id": 0})
    if not ep:
        raise HTTPException(404, "الحلقة غير موجودة")
    return ep

@api.post("/titles/{tid}/episodes")
async def create_episode(tid: str, data: EpisodeIn, _: dict = Depends(require_admin)):
    title = await db.titles.find_one({"id": tid})
    if not title:
        raise HTTPException(404, "العنوان غير موجود")
    eid = str(uuid.uuid4())
    doc = {
        "id": eid,
        "title_id": tid,
        "number": data.number,
        "name": data.name or "",
        "video_url": data.video_url or "",
        "pages": data.pages or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.episodes.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.delete("/titles/{tid}/episodes/{eid}")
async def delete_episode(tid: str, eid: str, _: dict = Depends(require_admin)):
    await db.episodes.delete_one({"id": eid, "title_id": tid})
    return {"ok": True}

# -------- MangaDex integration --------
MANGADEX_BASE = "https://api.mangadex.org"
MANGADEX_UPLOADS = "https://uploads.mangadex.org"

def _md_extract_title(attrs: dict) -> tuple[str, str]:
    titles = attrs.get("title") or {}
    alt_titles = attrs.get("altTitles") or []
    title_en = titles.get("en") or next(iter(titles.values()), "")
    title_ar = ""
    for at in alt_titles:
        if "ar" in at:
            title_ar = at["ar"]
            break
    return title_en or "Unknown", title_ar

def _md_extract_cover(rels: list) -> str:
    for r in rels:
        if r.get("type") == "cover_art":
            fn = (r.get("attributes") or {}).get("fileName")
            return fn or ""
    return ""

def _md_genres(tags: list) -> list:
    out = []
    for t in tags:
        n = ((t.get("attributes") or {}).get("name") or {}).get("en")
        if n:
            out.append(n)
    return out[:8]

async def _import_mangadex_batch(ttype: str, original_languages: list, total: int) -> int:
    """Bulk-import manga/manhwa metadata from MangaDex."""
    inserted = 0
    per_page = 100
    async with httpx.AsyncClient(timeout=30) as h:
        for offset in range(0, total, per_page):
            params = [
                ("limit", str(min(per_page, total - offset))),
                ("offset", str(offset)),
                ("availableTranslatedLanguage[]", "en"),
                ("contentRating[]", "safe"),
                ("contentRating[]", "suggestive"),
                ("order[followedCount]", "desc"),
                ("includes[]", "cover_art"),
            ]
            for lang in original_languages:
                params.append(("originalLanguage[]", lang))
            try:
                r = await h.get(f"{MANGADEX_BASE}/manga", params=params)
                r.raise_for_status()
            except Exception:
                logger.exception("MangaDex list failed at offset %s", offset)
                break
            data = r.json().get("data") or []
            if not data:
                break
            for item in data:
                md_id = item.get("id")
                if not md_id:
                    continue
                existing = await db.titles.find_one({"mangadex_id": md_id})
                if existing:
                    continue
                attrs = item.get("attributes") or {}
                title_en, title_ar = _md_extract_title(attrs)
                cover_fn = _md_extract_cover(item.get("relationships") or [])
                cover_url = f"{MANGADEX_UPLOADS}/covers/{md_id}/{cover_fn}.512.jpg" if cover_fn else ""
                desc = (attrs.get("description") or {}).get("en", "")
                status_map = {"completed": "completed", "ongoing": "ongoing", "hiatus": "ongoing", "cancelled": "completed"}
                doc = {
                    "id": str(uuid.uuid4()),
                    "mangadex_id": md_id,
                    "type": ttype,
                    "title": title_en,
                    "title_ar": title_ar,
                    "synopsis": desc[:1200],
                    "cover_url": cover_url,
                    "banner_url": cover_url,
                    "genres": _md_genres(attrs.get("tags") or []),
                    "status": status_map.get(attrs.get("status"), "ongoing"),
                    "episodes": None,
                    "chapters": attrs.get("lastChapter") and int(float(attrs["lastChapter"])) if (attrs.get("lastChapter") or "").replace(".", "").isdigit() else None,
                    "year": attrs.get("year"),
                    "rating_avg": 0,
                    "rating_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    await db.titles.insert_one(doc)
                    inserted += 1
                except Exception:
                    pass
    return inserted

async def _fetch_and_cache_mangadex_chapters(title: dict):
    """Fetch chapters list for a MangaDex title and store in episodes collection. Limit 200."""
    md_id = title.get("mangadex_id")
    if not md_id:
        return
    async with httpx.AsyncClient(timeout=30) as h:
        try:
            r = await h.get(
                f"{MANGADEX_BASE}/manga/{md_id}/feed",
                params=[
                    ("limit", "300"),
                    ("translatedLanguage[]", "en"),
                    ("order[chapter]", "asc"),
                    ("contentRating[]", "safe"),
                    ("contentRating[]", "suggestive"),
                ],
            )
            r.raise_for_status()
        except Exception:
            logger.exception("MangaDex chapters fetch failed for %s", md_id)
            return
        data = r.json().get("data") or []
        seen_numbers = set()
        for ch in data:
            attrs = ch.get("attributes") or {}
            ch_num_raw = attrs.get("chapter")
            try:
                ch_num = float(ch_num_raw) if ch_num_raw is not None else None
            except ValueError:
                ch_num = None
            if ch_num is None or ch_num in seen_numbers:
                continue
            seen_numbers.add(ch_num)
            await db.episodes.insert_one({
                "id": str(uuid.uuid4()),
                "title_id": title["id"],
                "mangadex_chapter_id": ch.get("id"),
                "number": ch_num,
                "name": attrs.get("title") or "",
                "video_url": "",
                "pages": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

@api.post("/admin/import_mangadex")
async def import_mangadex(ttype: str = "manga", total: int = 500, _: dict = Depends(require_admin)):
    if ttype not in ("manga", "manhwa"):
        raise HTTPException(400, "نوع غير صالح: manga أو manhwa فقط")
    langs = ["ja"] if ttype == "manga" else ["ko"]
    count = await _import_mangadex_batch(ttype, langs, min(total, 1000))
    return {"ok": True, "inserted": count}

@api.get("/proxy/image")
async def proxy_image(url: str):
    """Proxy MangaDex/MangaDex-CDN images through our backend to bypass
    referrer/rate-limit issues when loaded directly from the browser."""
    from fastapi.responses import Response
    allowed = ("mangadex.network", "mangadex.org")
    if not any(host in url for host in allowed):
        raise HTTPException(400, "URL غير مسموح")
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as h:
            # MangaDex serves the image fine to Python-default UA, but 403s fake browsers.
            r = await h.get(url)
            r.raise_for_status()
            return Response(
                content=r.content,
                media_type=r.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except httpx.HTTPError as e:
        raise HTTPException(502, f"تعذر جلب الصورة: {e}")

@api.get("/")
async def root():
    return {"ok": True, "name": "Otaku Hub"}

# -------- Startup --------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_TITLES = [
    {
        "type": "anime",
        "title": "Attack on Titan",
        "title_ar": "هجوم العمالقة",
        "synopsis": "في عالم تهاجمه عمالقة ضخمة، ينضم إيرن وأصدقاؤه إلى فيلق الاستطلاع لاكتشاف أسرار البشرية.",
        "cover_url": "https://images.unsplash.com/photo-1748445907524-2721462cc31a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHw0fHxjaW5lbWF0aWMlMjBhbmltZSUyMGNvdmVyfGVufDB8fHx8MTc3ODUwOTAzNnww&ixlib=rb-4.1.0&q=85",
        "genres": ["أكشن", "دراما", "فانتازيا"],
        "status": "completed",
        "episodes": 87,
        "year": 2013,
    },
    {
        "type": "manga",
        "title": "One Piece",
        "title_ar": "ون بيس",
        "synopsis": "لوفي وطاقمه يبحرون بحثاً عن الكنز الأسطوري ون بيس ليصبح ملك القراصنة.",
        "cover_url": "https://images.unsplash.com/photo-1755756383664-af3cf523242b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHwxfHxjaW5lbWF0aWMlMjBhbmltZSUyMGNvdmVyfGVufDB8fHx8MTc3ODUwOTAzNnww&ixlib=rb-4.1.0&q=85",
        "genres": ["مغامرة", "كوميديا", "أكشن"],
        "status": "ongoing",
        "chapters": 1100,
        "year": 1997,
    },
    {
        "type": "manhwa",
        "title": "Solo Leveling",
        "title_ar": "المستوى السولو",
        "synopsis": "صياد ضعيف يكتشف نظاماً سرياً يسمح له بالتطور وأن يصبح الأقوى.",
        "cover_url": "https://images.unsplash.com/photo-1757694010137-08c1ac1f697e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODl8MHwxfHNlYXJjaHwxfHxkYXJrJTIwbW9vZHklMjBmYW50YXN5JTIwbGFuZHNjYXBlfGVufDB8fHx8MTc3ODUwOTAzNnww&ixlib=rb-4.1.0&q=85",
        "genres": ["أكشن", "فانتازيا"],
        "status": "completed",
        "chapters": 200,
        "year": 2018,
    },
    {
        "type": "anime",
        "title": "Demon Slayer",
        "title_ar": "قاتل الشياطين",
        "synopsis": "تانجيرو يصبح قاتل شياطين بعد أن تتحول أخته إلى شيطانة، ويسعى لإعادتها بشرية.",
        "cover_url": "https://images.unsplash.com/photo-1542204165-65bf26472b9b?w=600&q=80",
        "genres": ["أكشن", "تاريخي", "خارق للطبيعة"],
        "status": "ongoing",
        "episodes": 55,
        "year": 2019,
    },
    {
        "type": "manhwa",
        "title": "Tower of God",
        "title_ar": "برج الإله",
        "synopsis": "بام يدخل البرج الغامض ليجد الفتاة التي تعني له كل شيء.",
        "cover_url": "https://images.unsplash.com/photo-1604079628040-94301bb21b91?w=600&q=80",
        "genres": ["مغامرة", "فانتازيا", "إثارة"],
        "status": "ongoing",
        "chapters": 600,
        "year": 2010,
    },
    {
        "type": "manga",
        "title": "Chainsaw Man",
        "title_ar": "رجل المنشار",
        "synopsis": "دينجي وكلب الشيطان بوتشيتا يصبحان رجل المنشار لصيد الشياطين.",
        "cover_url": "https://images.unsplash.com/photo-1626551093754-bf4ab57f5e22?w=600&q=80",
        "genres": ["أكشن", "رعب", "خارق للطبيعة"],
        "status": "ongoing",
        "chapters": 150,
        "year": 2018,
    },
]

@app.on_event("startup")
async def on_start():
    # indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.titles.create_index("id", unique=True)
    await db.messages.create_index([("room_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.episodes.create_index([("title_id", 1), ("number", 1)])

    # seed admin
    existing = await db.users.find_one({"email": ADMIN_EMAIL.lower()})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": ADMIN_EMAIL.lower(),
            "password_hash": hash_pw(ADMIN_PASSWORD),
            "name": "Admin",
            "avatar": "",
            "bio": "مدير المنصة",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Seeded admin user")

    # seed sample titles
    count = await db.titles.count_documents({})
    if count == 0:
        for t in SAMPLE_TITLES:
            tid = str(uuid.uuid4())
            doc = {**t,
                   "id": tid,
                   "banner_url": t.get("cover_url", ""),
                   "rating_avg": 0,
                   "rating_count": 0,
                   "created_at": datetime.now(timezone.utc).isoformat()}
            await db.titles.insert_one(doc)
        logger.info("Seeded sample titles")

    # seed sample episodes/chapters (separately, in case titles already exist)
    ep_count = await db.episodes.count_documents({})
    if ep_count == 0:
        # Only seed anime trailers (legit public content). Manga/manhwa chapters
        # must be added by admin via the panel since we can't host copyrighted pages.
        trailers = {
            "Attack on Titan": "https://www.youtube.com/embed/MGRm4IzK1SQ",
            "Demon Slayer": "https://www.youtube.com/embed/VQGCKyvzIM4",
        }
        all_titles = await db.titles.find({"type": "anime"}, {"_id": 0}).to_list(1000)
        for t in all_titles:
            url = trailers.get(t["title"], "")
            if not url:
                continue
            await db.episodes.insert_one({
                "id": str(uuid.uuid4()),
                "title_id": t["id"],
                "number": 0,
                "name": "تريلر رسمي",
                "video_url": url,
                "pages": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        logger.info("Seeded anime trailers")

@app.on_event("shutdown")
async def on_stop():
    client.close()

@api.get("/")
async def root():
    return {"ok": True, "name": "Otaku Hub"}
