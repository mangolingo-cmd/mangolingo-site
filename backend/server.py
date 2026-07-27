from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import bcrypt
import jwt
import httpx
from bson import ObjectId
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel, EmailStr, Field, field_validator

# -------- Config --------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-dev-secret-please")
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@otaku.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
fs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="uploads")

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
    aliases: List[str] = []   # أسماء بديلة: إنجليزي رسمي، روماجي، اختصارات...
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

from better_profanity import profanity

profanity.load_censor_words()  # القائمة الإنجليزية الجاهزة

# ضيف هنا كلمات إضافية بنفسك (عربي، لهجات محلية، أو أي كلمة إنجليزية ناقصة)
CUSTOM_BANNED_WORDS = [
    # مثال: "كلمة_سيئة_هنا",
]
if CUSTOM_BANNED_WORDS:
    profanity.add_censor_words(CUSTOM_BANNED_WORDS)

class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def no_banned_words(cls, v: str) -> str:
        if profanity.contains_profanity(v):
            raise ValueError("الرسالة تحتوي على كلمات غير مسموحة")
        return v

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    background: Optional[str] = None
    locale: Optional[str] = None

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
        "background": u.get("background") or "",
        "locale": u.get("locale") or "ar",
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

async def optional_user(request: Request) -> dict | None:
    """Returns the current user if authenticated, otherwise None.
    Never raises 401 — used for endpoints that work for both guests and logged-in users."""
    auth = request.headers.get("Authorization", "")
    token = None
    if auth.startswith("Bearer "):
        token = auth[7:]
    elif request.cookies.get("access_token"):
        token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
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

# Note: public GET /api/users/{uid} is declared further below — AFTER /users/search —
# to prevent route shadowing of the static `search` path.

# -------- Titles --------
@api.get("/titles")
async def list_titles(type: Optional[str] = None, q: Optional[str] = None, ar_only: bool = False, genre: Optional[str] = None, status: Optional[str] = None, sort_by: str = "newest", page: int = 1, limit: int = 30):
    # Exclude titles known to have no available chapters
    query = {"has_chapters": {"$ne": False}}
    if type:
        query["type"] = type
    if q:
        exact_query = {**query, "$or": [
            {"title": {"$regex": f"^{q}$", "$options": "i"}},
              {"title_ar": {"$regex": f"^{q}$", "$options": "i"}},
          {"aliases": {"$regex": f"^{q}$", "$options": "i"}},
      ]}
        if await db.titles.count_documents(exact_query) > 0:
            query = exact_query
        else:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
              {"title_ar": {"$regex": q, "$options": "i"}},
              {"aliases": {"$regex": q, "$options": "i"}},
          ]
    if ar_only:
        query["has_ar"] = True
    if genre:
        query["genres"] = genre
    if status:
        query["status"] = status
    page = max(1, page)
    limit = max(1, min(60, limit))
    skip = (page - 1) * limit
    total = await db.titles.count_documents(query)
    # Sort options: newest (created_at desc), rating (rating_avg desc), views (views_count desc)
    sort_spec = {
        "rating": [("rating_avg", -1), ("rating_count", -1)],
        "views": [("views_count", -1), ("created_at", -1)],
        "newest": [("has_ar", -1), ("created_at", -1)],
        "updated": [("last_episode_at", -1), ("created_at", -1)],
    }.get(sort_by, [("has_ar", -1), ("created_at", -1)])
    items = await db.titles.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(limit).to_list(limit)
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
    }

@api.get("/genres")
async def list_genres():
    pipeline = [
        {"$match": {"has_chapters": True}},
        {"$unwind": "$genres"},
        {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 40},
    ]
    items = await db.titles.aggregate(pipeline).to_list(60)
    return [{"name": g["_id"], "count": g["count"]} for g in items if g.get("_id")]

@api.get("/titles/{tid}")
async def get_title(tid: str):
    t = await db.titles.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "العنوان غير موجود")
    # Increment view counter (fire-and-forget)
    async def _bump():
        await db.titles.update_one({"id": tid}, {"$inc": {"views_count": 1}})
    asyncio.create_task(_bump())
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
async def update_title(tid: str, data: dict, _: dict = Depends(require_admin)):
    """Partial title update. Accepts any subset of title fields including 'status'
    so admins can toggle a manga between 'ongoing'/'completed'/'hiatus' from the UI."""
    allowed = {"title", "title_ar", "aliases", "synopsis", "cover_url", "genres",
               "status", "year", "type", "has_ar", "has_chapters"}
    update = {k: v for k, v in (data or {}).items() if k in allowed}
    if not update:
        raise HTTPException(400, "لا توجد حقول قابلة للتعديل")
    res = await db.titles.update_one({"id": tid}, {"$set": update})
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
    # update average using aggregation (avoids unbounded fetch)
    pipeline = [
        {"$match": {"title_id": tid}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    result = await db.reviews.aggregate(pipeline).to_list(1)
    if result:
        await db.titles.update_one(
            {"id": tid},
            {"$set": {"rating_avg": round(result[0]["avg"], 1), "rating_count": result[0]["count"]}},
        )
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

@api.get("/watchlist/{title_id}/check")
async def check_watchlist(title_id: str, user: dict = Depends(get_current_user)):
    """Returns {following: true/false, status: '...'} for the current user + given title."""
    w = await db.watchlist.find_one({"user_id": user["id"], "title_id": title_id}, {"_id": 0})
    return {"following": bool(w), "status": w.get("status") if w else None}

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
        "edited": False,
        "reactions": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    # Welcome bot: when a brand-new user posts their first message in lobby, the
    # bot replies once to make them feel at home.
    if room_id == "lobby":
        prior = await db.messages.count_documents({"sender_id": user["id"], "room_id": "lobby"})
        if prior == 1:
            bot = {
                "id": str(uuid.uuid4()),
                "room_id": "lobby",
                "sender_id": "bot",
                "sender_name": "MangaBot",
                "sender_avatar": "",
                "content": f"أهلاً {user.get('name','صديقي')}! 👋 مرحباً بك في الردهة. تقدر تناقش أعمالك المفضلة وتلتقي بعشاق الأنمي والمانجا. استمتع! 🎉",
                "edited": False,
                "reactions": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_bot": True,
            }
            await db.messages.insert_one(bot)
    return msg


class MessageEditIn(BaseModel):
    content: str

@api.patch("/messages/{mid}")
async def edit_message(mid: str, data: MessageEditIn, user: dict = Depends(get_current_user)):
    """Allow a user to edit their own message; bots/system messages can't be edited."""
    msg = await db.messages.find_one({"id": mid})
    if not msg:
        raise HTTPException(404, "الرسالة غير موجودة")
    if msg.get("sender_id") != user["id"]:
        raise HTTPException(403, "تقدر تعدّل رسائلك فقط")
    if not data.content.strip():
        raise HTTPException(400, "محتوى الرسالة فارغ")
    await db.messages.update_one(
        {"id": mid},
        {"$set": {
            "content": data.content,
            "edited": True,
            "edited_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return await db.messages.find_one({"id": mid}, {"_id": 0})

@api.delete("/messages/{mid}")
async def delete_message(mid: str, user: dict = Depends(get_current_user)):
    """Sender OR admin can delete a message."""
    msg = await db.messages.find_one({"id": mid})
    if not msg:
        raise HTTPException(404, "الرسالة غير موجودة")
    if msg.get("sender_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "غير مصرح")
    await db.messages.delete_one({"id": mid})
    return {"ok": True}


class ReactionIn(BaseModel):
    emoji: str

@api.post("/messages/{mid}/react")
async def react_message(mid: str, data: ReactionIn, user: dict = Depends(get_current_user)):
    """Toggle an emoji reaction on a message. reactions = { '👍': [user_id, ...] }."""
    emoji = (data.emoji or "").strip()
    if not emoji or len(emoji) > 8:
        raise HTTPException(400, "إيموجي غير صالح")
    msg = await db.messages.find_one({"id": mid})
    if not msg:
        raise HTTPException(404, "الرسالة غير موجودة")
    reactions = msg.get("reactions") or {}
    voters = reactions.get(emoji, [])
    if user["id"] in voters:
        voters = [v for v in voters if v != user["id"]]
    else:
        voters.append(user["id"])
    if voters:
        reactions[emoji] = voters
    else:
        reactions.pop(emoji, None)
    await db.messages.update_one({"id": mid}, {"$set": {"reactions": reactions}})
    return {"reactions": reactions}

# -------- DM helpers --------
@api.get("/dm/{uid}/room")
async def get_dm_room(uid: str, user: dict = Depends(get_current_user)):
    return {"room_id": dm_room_id(user["id"], uid)}

@api.get("/dm")
async def list_dms(user: dict = Depends(get_current_user)):
    # find all dm rooms involving user
    rooms = await db.messages.distinct("room_id", {"room_id": {"$regex": "^dm_"}})
    mine = [r for r in rooms if user["id"] in r[3:].split("_")]
    if not mine:
        return []
    # Batch-fetch all other users
    other_ids = [next(p for p in r[3:].split("_") if p != user["id"]) for r in mine]
    users = await db.users.find({"id": {"$in": other_ids}}, {"_id": 0}).to_list(len(other_ids))
    user_map = {u["id"]: u for u in users}
    # Batch-fetch last message per room
    pipeline = [
        {"$match": {"room_id": {"$in": mine}}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$room_id", "last": {"$first": "$$ROOT"}}},
    ]
    msg_docs = await db.messages.aggregate(pipeline).to_list(len(mine))
    msg_map = {m["_id"]: m["last"] for m in msg_docs}
    threads = []
    for r in mine:
        other_id = next(p for p in r[3:].split("_") if p != user["id"])
        other = user_map.get(other_id)
        last = msg_map.get(r)
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


# -------- Notification fan-out helper (used by scrapers / chapter creation) --------
async def notify_followers_new_chapter(title: dict, episode: dict):
    """Insert a 'new_chapter' notification for every user that has this title
    in their watchlist. Called whenever a new chapter is imported / created.
    Frontend SW polls /notifications and shows a desktop Notification."""
    if not title or not episode:
        return
    title_id = title.get("id")
    followers = await db.watchlist.find({"title_id": title_id}, {"user_id": 1, "_id": 0}).to_list(length=None)
    if not followers:
        return
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "title_id": title_id,
        "title_name": title.get("title_ar") or title.get("title"),
        "cover_url": title.get("cover_url"),
        "episode_id": episode.get("id"),
        "episode_number": episode.get("number"),
        "episode_name": episode.get("name"),
        "language": episode.get("language"),
    }
    docs = [
        {
            "id": str(uuid.uuid4()),
            "user_id": f["user_id"],
            "type": "new_chapter",
            "payload": payload,
            "read": False,
            "created_at": now,
        }
        for f in followers
    ]
    if docs:
        await db.notifications.insert_many(docs, ordered=False)

# -------- Episodes / Chapters --------
class EpisodeIn(BaseModel):
    number: float
    name: Optional[str] = ""
    video_url: Optional[str] = ""  # for anime
    pages: List[str] = []           # for manga/manhwa

@api.get("/titles/{tid}/episodes")
async def list_episodes(tid: str, lang: str = "en"):
    title = await db.titles.find_one({"id": tid}, {"_id": 0})
    if not title:
        raise HTTPException(404, "العنوان غير موجود")
    # Lazy-load this language if never fetched
    if title.get("mangadex_id") and lang not in (title.get("langs_fetched") or []):
        await _fetch_and_cache_mangadex_chapters(title, lang)
    # Return only chapters in the requested language (no cross-language mixing)
    if lang == "en":
        # Legacy episodes without language field are treated as English
        query = {"title_id": tid, "$or": [{"language": "en"}, {"language": {"$exists": False}}]}
    else:
        query = {"title_id": tid, "language": lang}
    # Numeric ordering (1, 2, 3, ... 10, 11) using collation — prevents lexicographic
    # jumps like 1, 10, 11, ... 2, 20.
    items = (
        await db.episodes.find(query, {"_id": 0})
        .collation({"locale": "en_US", "numericOrdering": True})
        .sort("number", 1)
        .to_list(5000)
    )
    return items

@api.get("/titles/{tid}/languages")
async def list_languages(tid: str):
    """Return list of languages that have chapters for this title."""
    title = await db.titles.find_one({"id": tid}, {"_id": 0})
    if not title:
        raise HTTPException(404, "العنوان غير موجود")
    langs = await db.episodes.distinct("language", {"title_id": tid})
    # Also include legacy episodes that have no language field (treat as en)
    legacy = await db.episodes.count_documents({"title_id": tid, "language": {"$exists": False}})
    if legacy and "en" not in langs:
        langs.append("en")
    return {"languages": [lang for lang in langs if lang]}

@api.get("/episodes/{eid}/pages")
async def get_episode_pages(eid: str):
    """Return live page image URLs. Public — no auth required for reading."""
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
        except Exception:
            logger.exception("MangaDex pages fetch failed")
            raise HTTPException(502, "تعذر جلب الصفحات من المصدر")
    return {"pages": ep.get("pages", [])}

@api.get("/titles/{tid}/episodes/{eid}")
async def get_episode(tid: str, eid: str):
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
    await db.titles.update_one({"id": tid}, {"$max": {"last_episode_at": doc["created_at"]}})
    # Notify all watchlist followers about the new chapter
    title = await db.titles.find_one({"id": tid}, {"_id": 0})
    asyncio.create_task(notify_followers_new_chapter(title, doc))
    return doc

@api.delete("/titles/{tid}/episodes/{eid}")
async def delete_episode(tid: str, eid: str, _: dict = Depends(require_admin)):
    await db.episodes.delete_one({"id": eid, "title_id": tid})
    return {"ok": True}

# -------- Reading progress (Continue Reading) --------
class ProgressIn(BaseModel):
    title_id: str
    episode_id: str
    episode_number: float | int | None = None
    page: int = 0

@api.post("/reading/progress")
async def save_progress(data: ProgressIn, user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    await db.reading_progress.update_one(
        {"user_id": user["id"], "title_id": data.title_id},
        {"$set": {
            "user_id": user["id"],
            "title_id": data.title_id,
            "episode_id": data.episode_id,
            "episode_number": data.episode_number,
            "page": data.page,
            "updated_at": now,
        }},
        upsert=True,
    )
    return {"ok": True}

@api.get("/reading/continue")
async def list_continue(user: dict = Depends(get_current_user)):
    """Return up to 12 most-recently-read titles with their last episode info."""
    cur = db.reading_progress.find({"user_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).limit(12)
    items = await cur.to_list(length=12)
    out = []
    for it in items:
        title = await db.titles.find_one({"id": it["title_id"]}, {"_id": 0})
        if not title:
            continue
        out.append({
            "title_id": it["title_id"],
            "episode_id": it["episode_id"],
            "episode_number": it.get("episode_number"),
            "page": it.get("page", 0),
            "updated_at": it.get("updated_at"),
            "title": title,
        })
    return out

@api.get("/reading/progress/{title_id}")
async def get_progress(title_id: str, user: dict = Depends(get_current_user)):
    p = await db.reading_progress.find_one({"user_id": user["id"], "title_id": title_id}, {"_id": 0})
    return p or {}

@api.delete("/reading/progress/{title_id}")
async def delete_progress(title_id: str, user: dict = Depends(get_current_user)):
    await db.reading_progress.delete_one({"user_id": user["id"], "title_id": title_id})
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

async def _import_mangadex_batch(ttype: str, original_languages: list, total: int, start_offset: int = 0, order: str = "followedCount") -> int:
    """Bulk-import manga/manhwa metadata from MangaDex."""
    inserted = 0
    per_page = 100
    async with httpx.AsyncClient(timeout=30) as h:
        for offset in range(start_offset, start_offset + total, per_page):
            params = [
                ("limit", str(min(per_page, start_offset + total - offset))),
                ("offset", str(offset)),
                ("availableTranslatedLanguage[]", "en"),
                ("contentRating[]", "safe"),
                ("contentRating[]", "suggestive"),
                (f"order[{order}]", "desc"),
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

async def _fetch_and_cache_mangadex_chapters(title: dict, lang: str = "en"):
    """Fetch all chapters for a MangaDex title in given language (with pagination)."""
    md_id = title.get("mangadex_id")
    if not md_id:
        return
    seen_numbers = set()
    inserted = 0
    async with httpx.AsyncClient(timeout=30) as h:
        offset = 0
        while True:
            try:
                r = await h.get(
                    f"{MANGADEX_BASE}/manga/{md_id}/feed",
                    params=[
                        ("limit", "500"),
                        ("offset", str(offset)),
                        ("translatedLanguage[]", lang),
                        ("order[chapter]", "asc"),
                        ("contentRating[]", "safe"),
                        ("contentRating[]", "suggestive"),
                    ],
                )
                r.raise_for_status()
            except Exception:
                logger.exception("MangaDex chapters fetch failed for %s lang=%s offset=%s", md_id, lang, offset)
                break
            body = r.json()
            data = body.get("data") or []
            if not data:
                break
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
                    "language": lang,
                    "video_url": "",
                    "pages": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                inserted += 1
            total = body.get("total", 0)
            offset += len(data)
            if offset >= total:
                break
    # Mark this language as fetched (so we don't retry empty fetches)
    update = {"$addToSet": {"langs_fetched": lang}}
    if lang == "ar" and inserted > 0:
        update["$set"] = {"has_ar": True}
    if inserted > 0:
        update["$max"] = {"last_episode_at": datetime.now(timezone.utc).isoformat()}
    await db.titles.update_one({"id": title["id"]}, update)
    return inserted

@api.post("/admin/import_mangadex")
async def import_mangadex(ttype: str = "manga", total: int = 500, order: str = "followedCount", _: dict = Depends(require_admin)):
    if ttype not in ("manga", "manhwa", "manhua"):
        raise HTTPException(400, "نوع غير صالح: manga أو manhwa أو manhua فقط")
    langs = {"manga": ["ja"], "manhwa": ["ko"], "manhua": ["zh", "zh-hk"]}[ttype]
    # Skip past titles we've already imported for this type — fetch the next batch
    existing = await db.titles.count_documents({"type": ttype, "mangadex_id": {"$exists": True}})
    count = await _import_mangadex_batch(ttype, langs, min(total, 1000), start_offset=existing if order == "followedCount" else 0, order=order)
    return {"ok": True, "inserted": count, "started_at_offset": existing}

@api.post("/admin/cleanup_empty")
async def cleanup_empty(_: dict = Depends(require_admin)):
    """Scan all MangaDex-linked titles, fetch English chapters, hide titles
    with no chapters or fewer than 5 EN/AR chapters (sparse coverage)."""
    import asyncio
    titles_to_check = await db.titles.find(
        {"mangadex_id": {"$exists": True}, "has_chapters": {"$ne": False}},
        {"_id": 0, "id": 1, "mangadex_id": 1, "title": 1},
    ).to_list(10000)

    sem = asyncio.Semaphore(8)
    empty = []
    sparse = []
    fetched = []

    async def check(t):
        async with sem:
            existing = await db.episodes.count_documents({"title_id": t["id"]})
            if existing == 0:
                await _fetch_and_cache_mangadex_chapters(t, "en")
            cnt = await db.episodes.count_documents({
                "title_id": t["id"],
                "$or": [{"language": "en"}, {"language": "ar"}, {"language": {"$exists": False}}],
            })
            if cnt == 0:
                await db.titles.update_one({"id": t["id"]}, {"$set": {"has_chapters": False}})
                empty.append(t["id"])
            elif cnt < 20:
                await db.titles.update_one({"id": t["id"]}, {"$set": {"has_chapters": False, "sparse": True}})
                sparse.append(t["id"])
            else:
                await db.titles.update_one({"id": t["id"]}, {"$set": {"has_chapters": True}})
                fetched.append(t["id"])

    await asyncio.gather(*[check(t) for t in titles_to_check])
    return {"checked": len(titles_to_check), "with_chapters": len(fetched), "without_chapters": len(empty), "sparse_hidden": len(sparse)}

@api.post("/admin/fetch_language")
async def fetch_language(lang: str = "ar", _: dict = Depends(require_admin)):
    """Bulk-fetch chapters in a given language for ALL visible titles."""
    import asyncio
    titles = await db.titles.find(
        {"mangadex_id": {"$exists": True}, "has_chapters": True, "langs_fetched": {"$ne": lang}},
        {"_id": 0, "id": 1, "mangadex_id": 1},
    ).to_list(5000)

    sem = asyncio.Semaphore(6)
    counts = {"with": 0, "without": 0}

    async def fetch(t):
        async with sem:
            before = await db.episodes.count_documents({"title_id": t["id"], "language": lang})
            await _fetch_and_cache_mangadex_chapters(t, lang)
            after = await db.episodes.count_documents({"title_id": t["id"], "language": lang})
            if after > before:
                counts["with"] += 1
            else:
                counts["without"] += 1

    await asyncio.gather(*[fetch(t) for t in titles])
    return {"checked": len(titles), "got_chapters": counts["with"], "no_chapters_in_lang": counts["without"]}

@api.get("/proxy/image")
async def proxy_image(url: str):
    """Proxy MangaDex/MangaSpark images through our backend to bypass
    referrer/rate-limit issues when loaded directly from the browser."""
    from fastapi.responses import Response
    allowed = ("mangadex.network", "mangadex.org", "manga-spark.net", "manga-spark.com", "olympustaff.com")
    if not any(host in url for host in allowed):
        raise HTTPException(400, "URL غير مسموح")
    # manga-spark CDN requires browser UA + referer (Cloudflare protected)
    headers = {}
    if "manga-spark" in url:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
            "Referer": "https://manga-spark.net/",
            "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
        }
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as h:
            r = await h.get(url, headers=headers)
            r.raise_for_status()
            return Response(
                content=r.content,
                media_type=r.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except httpx.HTTPError as e:
        raise HTTPException(502, f"تعذر جلب الصورة: {e}")

# -------- Image uploads (GridFS) --------
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

@api.post("/uploads/image")
async def upload_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a user image (avatar / profile background) to MongoDB GridFS.
    Returns a public URL that can be stored in user.avatar / user.background."""
    if file.content_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(400, "نوع الملف غير مدعوم. استخدم PNG, JPEG, WebP أو GIF.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "حجم الصورة يتجاوز 5 ميغابايت.")
    if not data:
        raise HTTPException(400, "ملف فارغ.")
    object_id = await fs_bucket.upload_from_stream(
        file.filename or "upload",
        data,
        metadata={
            "content_type": file.content_type,
            "owner_id": user["id"],
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"url": f"/api/uploads/{object_id}", "id": str(object_id), "size": len(data)}

@api.get("/uploads/{file_id}")
async def get_upload(file_id: str):
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(404, "غير موجود")
    try:
        stream = await fs_bucket.open_download_stream(oid)
    except Exception:
        raise HTTPException(404, "الصورة غير موجودة")
    ct = (stream.metadata or {}).get("content_type", "application/octet-stream")
    async def gen():
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk
    return StreamingResponse(gen(), media_type=ct, headers={"Cache-Control": "public, max-age=31536000, immutable"})

# -------- Startup --------
@api.post("/admin/refresh-mangaspark")
async def admin_refresh_mangaspark(_: dict = Depends(require_admin)):
    """Manually trigger an immediate manga-spark chapter refresh.
    Runs in background — poll /api/admin/job-status?kind=mangaspark_refresh_manual."""
    from scrape_mangaspark import refresh_all_chapters

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.system_logs.insert_one({
        "kind": "mangaspark_refresh_manual",
        "job_id": job_id,
        "status": "running",
        "at": now,
        "started_at": now,
        "titles_scanned": 0,
        "new_chapters": 0,
    })

    async def _worker():
        try:
            from scrape_olympustaff import site_alive, refresh_latest as olympus_refresh
            stats = {"titles_scanned": 0, "new_chapters": 0}
            if await site_alive("https://manga-spark.net/"):
                s1 = await refresh_all_chapters(db_arg=db)
                stats["titles_scanned"] += s1.get("titles_scanned", 0)
                stats["new_chapters"] += s1.get("new_chapters", 0)
            else:
                logger.warning("[refresh] manga-spark.net unreachable — skipped")
            s2 = await olympus_refresh(db, max_chapters=300)
            stats["titles_scanned"] += s2.get("titles_scanned", 0)
            stats["new_chapters"] += s2.get("new_chapters", 0)
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    **stats,
                }},
            )
            logger.info(f"[refresh-mangaspark {job_id}] done {stats}")
        except Exception as e:
            logger.exception(f"[refresh-mangaspark {job_id}] failed")
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500],
                          "finished_at": datetime.now(timezone.utc).isoformat()}},
            )

    asyncio.create_task(_worker())
    return {"status": "processing", "job_id": job_id,
            "poll_url": "/api/admin/job-status?kind=mangaspark_refresh_manual"}

# -------- Production maintenance endpoints (admin-only) --------
@api.post("/admin/import-olympustaff")
async def admin_import_olympustaff(max_new_titles: int = 10, max_chapters: int = 400, _: dict = Depends(require_admin)):
    """Smart import from olympustaff.com: fills missing chapters for matched titles
    and imports up to `max_new_titles` new titles. Re-runnable — each run continues
    where the previous stopped. Poll /admin/job-status?kind=admin_olympus_import."""
    from scrape_olympustaff import smart_import

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.system_logs.insert_one({
        "kind": "admin_olympus_import",
        "job_id": job_id,
        "status": "running",
        "at": now,
        "started_at": now,
        "catalog_total": 0,
        "scanned": 0,
        "matched": 0,
        "new_titles": 0,
        "chapters_added": 0,
    })

    async def _progress(stats: dict):
        await db.system_logs.update_one({"job_id": job_id}, {"$set": stats})

    async def _worker():
        try:
            stats = await smart_import(db, progress_cb=_progress,
                                       max_new_titles=max_new_titles, max_chapters=max_chapters)
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "done", "finished_at": datetime.now(timezone.utc).isoformat(), **stats}},
            )
            logger.info(f"[olympus-import {job_id}] done {stats}")
        except Exception as e:
            logger.exception(f"[olympus-import {job_id}] failed")
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500],
                          "finished_at": datetime.now(timezone.utc).isoformat()}},
            )

    asyncio.create_task(_worker())
    return {"status": "processing", "job_id": job_id,
            "poll_url": "/api/admin/job-status?kind=admin_olympus_import"}


@api.post("/admin/dedupe-titles")
async def admin_dedupe_titles(_: dict = Depends(require_admin)):
    """Merge duplicate titles (same source_slug). Runs in background — poll
    /admin/job-status?kind=admin_dedupe."""
    from collections import defaultdict
    from pymongo import DeleteOne, UpdateOne

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.system_logs.insert_one({
        "kind": "admin_dedupe",
        "job_id": job_id,
        "status": "running",
        "at": now,
        "started_at": now,
        "merged_titles": 0,
        "placeholders_deleted": 0,
        "moved_chapters": 0,
        "dropped_duplicate_chapters": 0,
    })

    async def _worker():
        try:
            titles = await db.titles.find({}, {"_id": 0}).to_list(length=None)
            groups: dict = defaultdict(list)
            for t in titles:
                slug = (t.get("source_slug") or "").strip().lower()
                ttype = (t.get("type") or "").strip().lower()
                title_norm = (t.get("title") or "").strip().lower()
                key = (slug, ttype) if slug else (f"name:{title_norm}", ttype)
                groups[key].append(t)

            # Pre-count episodes for all duplicate-group titles in one $group aggregation
            dupe_title_ids = [t["id"] for items in groups.values() if len(items) > 1 for t in items]
            ep_counts: dict = {}
            if dupe_title_ids:
                async for row in db.episodes.aggregate([
                    {"$match": {"title_id": {"$in": dupe_title_ids}}},
                    {"$group": {"_id": "$title_id", "n": {"$sum": 1}}},
                ]):
                    ep_counts[row["_id"]] = row["n"]

            merged_titles = 0
            moved_chapters = 0
            dropped_chapters = 0
            BATCH = 500

            for items in groups.values():
                if len(items) < 2:
                    continue
                counts = [(ep_counts.get(t["id"], 0), t) for t in items]
                counts.sort(key=lambda x: (-x[0], x[1].get("created_at", "")))
                keeper = counts[0][1]

                existing_keys = set()
                async for ep in db.episodes.find(
                    {"title_id": keeper["id"]}, {"number": 1, "language": 1}
                ):
                    existing_keys.add((ep.get("number"), ep.get("language", "ar")))

                ep_ops: list = []
                async def flush_ep_ops():
                    nonlocal ep_ops
                    if ep_ops:
                        await db.episodes.bulk_write(ep_ops, ordered=False)
                        ep_ops = []

                for _, dupe in counts[1:]:
                    async for ep in db.episodes.find(
                        {"title_id": dupe["id"]}, {"_id": 1, "number": 1, "language": 1}
                    ):
                        k = (ep.get("number"), ep.get("language", "ar"))
                        if k in existing_keys:
                            ep_ops.append(DeleteOne({"_id": ep["_id"]}))
                            dropped_chapters += 1
                        else:
                            ep_ops.append(UpdateOne(
                                {"_id": ep["_id"]},
                                {"$set": {"title_id": keeper["id"]}},
                            ))
                            existing_keys.add(k)
                            moved_chapters += 1
                        if len(ep_ops) >= BATCH:
                            await flush_ep_ops()
                    await db.watchlist.update_many({"title_id": dupe["id"]}, {"$set": {"title_id": keeper["id"]}})
                    await db.reviews.update_many({"title_id": dupe["id"]}, {"$set": {"title_id": keeper["id"]}})
                    await db.reading_progress.update_many({"title_id": dupe["id"]}, {"$set": {"title_id": keeper["id"]}})
                    await db.titles.delete_one({"id": dupe["id"]})
                    merged_titles += 1
                await flush_ep_ops()
                # progress
                await db.system_logs.update_one(
                    {"job_id": job_id},
                    {"$set": {
                        "merged_titles": merged_titles,
                        "moved_chapters": moved_chapters,
                        "dropped_duplicate_chapters": dropped_chapters,
                    }},
                )

            # Delete stale empty placeholders sharing a name with a populated title
            titles2 = await db.titles.find({}, {"_id": 0, "id": 1, "title": 1}).to_list(length=None)
            ep_counts_all: dict = {}
            async for row in db.episodes.aggregate([
                {"$group": {"_id": "$title_id", "n": {"$sum": 1}}},
            ]):
                ep_counts_all[row["_id"]] = row["n"]

            name_map: dict = {}
            for t in titles2:
                n = (t.get("title") or "").strip().lower()
                if not n:
                    continue
                name_map.setdefault(n, []).append((t["id"], ep_counts_all.get(t["id"], 0)))

            placeholders_deleted = 0
            to_del: list = []
            for _, lst in name_map.items():
                if len(lst) < 2 or not any(c > 0 for _, c in lst):
                    continue
                for tid, cnt in lst:
                    if cnt == 0:
                        to_del.append(tid)
            for i in range(0, len(to_del), 500):
                chunk = to_del[i : i + 500]
                await db.titles.delete_many({"id": {"$in": chunk}})
                await db.watchlist.delete_many({"title_id": {"$in": chunk}})
                await db.reviews.delete_many({"title_id": {"$in": chunk}})
                await db.reading_progress.delete_many({"title_id": {"$in": chunk}})
                placeholders_deleted += len(chunk)

            titles_remaining = await db.titles.count_documents({})
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "merged_titles": merged_titles,
                    "placeholders_deleted": placeholders_deleted,
                    "moved_chapters": moved_chapters,
                    "dropped_duplicate_chapters": dropped_chapters,
                    "titles_remaining": titles_remaining,
                }},
            )
            logger.info(f"[dedupe {job_id}] done merged={merged_titles} ph={placeholders_deleted} remaining={titles_remaining}")
        except Exception as e:
            logger.exception(f"[dedupe {job_id}] failed")
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500],
                          "finished_at": datetime.now(timezone.utc).isoformat()}},
            )

    asyncio.create_task(_worker())
    return {"status": "processing", "job_id": job_id, "poll_url": "/api/admin/job-status?kind=admin_dedupe"}


@api.post("/admin/fix-missing-covers")
async def admin_fix_missing_covers(_: dict = Depends(require_admin)):
    """Fix titles with empty covers OR dead manga-spark.net covers.
    Uses MangaDex Cover API when mangadex_id is known, otherwise searches
    MangaDex by title. Runs in background — poll /admin/job-status?kind=admin_fix_covers."""
    from pymongo import UpdateOne

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    dead_cover = {"$or": [
        {"cover_url": ""}, {"cover_url": None}, {"cover_url": {"$exists": False}},
        {"cover_url": {"$regex": r"manga-spark\.net"}},
    ]}
    missing = await db.titles.find(
        {"mangadex_id": {"$exists": True, "$nin": [None, ""]}, **dead_cover},
        {"_id": 0, "id": 1, "mangadex_id": 1},
    ).to_list(length=None)
    no_mdid = await db.titles.find(
        {"$and": [
            {"$or": [{"mangadex_id": {"$exists": False}}, {"mangadex_id": {"$in": [None, ""]}}]},
            dead_cover,
        ]},
        {"_id": 0, "id": 1, "title": 1, "title_ar": 1},
    ).to_list(length=None)

    await db.system_logs.insert_one({
        "kind": "admin_fix_covers",
        "job_id": job_id,
        "status": "running",
        "at": now,
        "started_at": now,
        "scanned": len(missing) + len(no_mdid),
        "covers_updated": 0,
    })

    async def _worker():
        try:
            updated = 0
            async with httpx.AsyncClient(timeout=20) as c:
                for start in range(0, len(missing), 50):
                    batch = missing[start : start + 50]
                    params = [("manga[]", t["mangadex_id"]) for t in batch] + [("limit", 100)]
                    r = await c.get("https://api.mangadex.org/cover", params=params)
                    if r.status_code != 200:
                        continue
                    cov_by_mid: dict = {}
                    for item in r.json().get("data", []):
                        fn = item.get("attributes", {}).get("fileName")
                        if not fn:
                            continue
                        for rel in item.get("relationships", []):
                            if rel.get("type") == "manga" and rel["id"] not in cov_by_mid:
                                cov_by_mid[rel["id"]] = (
                                    f"https://uploads.mangadex.org/covers/{rel['id']}/{fn}.512.jpg"
                                )
                                break
                    ops = []
                    for t in batch:
                        url = cov_by_mid.get(t["mangadex_id"])
                        if url:
                            ops.append(UpdateOne({"id": t["id"]}, {"$set": {"cover_url": url}}))
                    if ops:
                        result = await db.titles.bulk_write(ops, ordered=False)
                        updated += result.modified_count
                    await db.system_logs.update_one(
                        {"job_id": job_id},
                        {"$set": {"covers_updated": updated, "progress": start + len(batch)}},
                    )
                    await asyncio.sleep(0.3)

                # Phase 2: titles without mangadex_id — search MangaDex by name
                searched_found = 0
                for i, t in enumerate(no_mdid):
                    name = t.get("title") or t.get("title_ar") or ""
                    if not name:
                        continue
                    try:
                        r = await c.get(
                            "https://api.mangadex.org/manga",
                            params=[
                                ("title", name), ("limit", 3), ("includes[]", "cover_art"),
                                ("contentRating[]", "safe"), ("contentRating[]", "suggestive"), ("contentRating[]", "erotica"),
                                ("order[relevance]", "desc"),
                            ],
                        )
                        if r.status_code != 200:
                            await asyncio.sleep(1.0)
                            continue
                        for item in r.json().get("data", []):
                            fn = next(
                                (rel.get("attributes", {}).get("fileName")
                                 for rel in item.get("relationships", []) if rel.get("type") == "cover_art"),
                                None,
                            )
                            if fn:
                                await db.titles.update_one(
                                    {"id": t["id"]},
                                    {"$set": {
                                        "cover_url": f"https://uploads.mangadex.org/covers/{item['id']}/{fn}.512.jpg",
                                        "mangadex_id": item["id"],
                                    }},
                                )
                                updated += 1
                                searched_found += 1
                                break
                    except Exception:
                        pass
                    if i % 10 == 0:
                        await db.system_logs.update_one(
                            {"job_id": job_id},
                            {"$set": {"covers_updated": updated, "progress": len(missing) + i}},
                        )
                    await asyncio.sleep(0.35)
            still_missing = await db.titles.count_documents(
                {"$or": [
                    {"cover_url": ""}, {"cover_url": None}, {"cover_url": {"$exists": False}},
                    {"cover_url": {"$regex": r"manga-spark\.net"}},
                ]}
            )
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "done",
                    "covers_updated": updated,
                    "search_matched": searched_found,
                    "still_missing": still_missing,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            logger.info(f"[fix-covers {job_id}] done updated={updated} still_missing={still_missing}")
        except Exception as e:
            logger.exception(f"[fix-covers {job_id}] failed")
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500],
                          "finished_at": datetime.now(timezone.utc).isoformat()}},
            )

    asyncio.create_task(_worker())
    return {
        "status": "processing",
        "job_id": job_id,
        "scanned": len(missing),
        "poll_url": "/api/admin/job-status?kind=admin_fix_covers",
    }


async def _backfill_last_episode_at():
    """Set titles.last_episode_at = max(episodes.created_at) per title. Idempotent."""
    from pymongo import UpdateOne
    pipeline = [{"$group": {"_id": "$title_id", "last": {"$max": "$created_at"}}}]
    ops = []
    async for g in db.episodes.aggregate(pipeline):
        if g.get("_id") and g.get("last"):
            ops.append(UpdateOne({"id": g["_id"]}, {"$max": {"last_episode_at": g["last"]}}))
        if len(ops) >= 1000:
            await db.titles.bulk_write(ops, ordered=False)
            ops = []
    if ops:
        await db.titles.bulk_write(ops, ordered=False)


LANG_TO_TYPE = {"ja": "manga", "ko": "manhwa", "zh": "manhua", "zh-hk": "manhua", "zh-tw": "manhua"}


@api.post("/admin/reclassify-types")
async def admin_reclassify_types(_: dict = Depends(require_admin)):
    """Fix title types (manga/manhwa/manhua) from MangaDex originalLanguage.
    Runs in background — poll /admin/job-status?kind=admin_reclassify_types."""
    from pymongo import UpdateOne

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    targets = await db.titles.find(
        {"mangadex_id": {"$exists": True, "$nin": [None, ""]}},
        {"_id": 0, "id": 1, "mangadex_id": 1, "type": 1},
    ).to_list(length=None)

    await db.system_logs.insert_one({
        "kind": "admin_reclassify_types",
        "job_id": job_id,
        "status": "running",
        "at": now,
        "started_at": now,
        "scanned": len(targets),
        "reclassified": 0,
        "manhua_found": 0,
    })

    async def _worker():
        try:
            changed = 0
            manhua = 0
            async with httpx.AsyncClient(timeout=25) as c:
                for start in range(0, len(targets), 100):
                    batch = targets[start : start + 100]
                    params = [("ids[]", t["mangadex_id"]) for t in batch] + [
                        ("limit", 100),
                        ("contentRating[]", "safe"), ("contentRating[]", "suggestive"), ("contentRating[]", "erotica"),
                    ]
                    try:
                        r = await c.get("https://api.mangadex.org/manga", params=params)
                        if r.status_code != 200:
                            await asyncio.sleep(1.5)
                            continue
                        lang_by_mid = {
                            item["id"]: (item.get("attributes") or {}).get("originalLanguage", "")
                            for item in r.json().get("data", [])
                        }
                    except Exception:
                        await asyncio.sleep(1.5)
                        continue
                    ops = []
                    for t in batch:
                        new_type = LANG_TO_TYPE.get(lang_by_mid.get(t["mangadex_id"], ""))
                        if new_type and new_type != t.get("type"):
                            ops.append(UpdateOne({"id": t["id"]}, {"$set": {"type": new_type}}))
                            changed += 1
                            if new_type == "manhua":
                                manhua += 1
                    if ops:
                        await db.titles.bulk_write(ops, ordered=False)
                    await db.system_logs.update_one(
                        {"job_id": job_id},
                        {"$set": {"reclassified": changed, "manhua_found": manhua, "progress": start + len(batch)}},
                    )
                    await asyncio.sleep(0.5)
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "done",
                    "reclassified": changed,
                    "manhua_found": manhua,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            logger.info(f"[reclassify-types {job_id}] done changed={changed} manhua={manhua}")
        except Exception as e:
            logger.exception(f"[reclassify-types {job_id}] failed")
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500],
                          "finished_at": datetime.now(timezone.utc).isoformat()}},
            )

    asyncio.create_task(_worker())
    return {
        "status": "processing",
        "job_id": job_id,
        "scanned": len(targets),
        "poll_url": "/api/admin/job-status?kind=admin_reclassify_types",
    }


@api.get("/admin/job-status")
async def admin_job_status(kind: str, _: dict = Depends(require_admin)):
    """Generic status poll for admin background jobs.
    kind: admin_dedupe | admin_fix_covers | admin_import_bundle"""
    if kind not in {"admin_dedupe", "admin_fix_covers", "admin_import_bundle", "mangaspark_refresh_manual", "admin_reclassify_types", "admin_olympus_import"}:
        raise HTTPException(400, "Invalid kind")
    log = await db.system_logs.find_one(
        {"kind": kind}, {"_id": 0}, sort=[("started_at", -1)]
    )
    if not log:
        return {"status": "idle"}
    return log


@api.post("/admin/import-mangaspark-bundle")
async def admin_import_mangaspark_bundle(_: dict = Depends(require_admin)):
    """Load /app/backend/seed/mangaspark_export.json.gz and bulk-upsert into MongoDB.
    Runs in background to avoid proxy timeout. Poll /admin/import-bundle/status."""
    import gzip
    import json
    from pymongo import ReplaceOne

    path = os.path.join(os.path.dirname(__file__), "seed", "mangaspark_export.json.gz")
    if not os.path.exists(path):
        raise HTTPException(404, f"Bundle not found at {path}")

    # Read & parse synchronously (fast — only 2.5MB)
    with open(path, "rb") as f:
        bundle = json.loads(gzip.decompress(f.read()))
    titles = bundle.get("titles", [])
    episodes = bundle.get("episodes", [])
        # حقن الـ 20 مانهوا الجديدة لضمان ضخها بالكامل في قاعدة البيانات الحية
    new_slugs = ["the-indomitable-martial-king", "the-knight-king-who-returned-with-a-god", "the-max-level-hero-has-returned", "the-nebula-s-civilization", "necromancers-evolutionary-traits", "genius-of-the-unique-lineage", "the-lords-coins-of-reincarnation", "steel-eating-player", "god-of-blackfield", "past-life-regressor", "infinite-level-up-in-murim", "reincarnated-as-an-unruly-heir", "worlds-best-assassin", "absolute-martial-arts", "martial-peak", "apocalypse-online", "the-challenger", "auto-hunting-with-clones", "top-corner"]
    for s in new_slugs:
        if not any(t.get("id") == s for t in titles):
            titles.append({"id": s, "title": s.replace("-", " ").title(), "source": "mangaspark"})


    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.system_logs.insert_one({
        "kind": "admin_import_bundle",
        "job_id": job_id,
        "status": "running",
        "at": now,
        "started_at": now,
        "titles_total": len(titles),
        "episodes_total": len(episodes),
        "titles_upserted": 0,
        "chapters_inserted": 0,
        "exported_at": bundle.get("exported_at"),
    })

    async def _worker():
        try:
            # 1) Upsert titles in batches of 500 via bulk_write
            BATCH = 500
            done_t = 0
            for i in range(0, len(titles), BATCH):
                chunk = titles[i : i + BATCH]
                ops = [ReplaceOne({"id": t["id"]}, t, upsert=True) for t in chunk]
                if ops:
                    await db.titles.bulk_write(ops, ordered=False)
                done_t += len(chunk)
                await db.system_logs.update_one(
                    {"job_id": job_id}, {"$set": {"titles_upserted": done_t}}
                )

            # 2) Wipe any existing episodes for these titles (single bulk delete)
            title_ids = [t["id"] for t in titles]
            for i in range(0, len(title_ids), 500):
                await db.episodes.delete_many({"title_id": {"$in": title_ids[i : i + 500]}})

            # 3) Insert episodes in batches of 500
            done_e = 0
            for i in range(0, len(episodes), BATCH):
                chunk = episodes[i : i + BATCH]
                if chunk:
                    await db.episodes.insert_many(chunk, ordered=False)
                done_e += len(chunk)
                await db.system_logs.update_one(
                    {"job_id": job_id}, {"$set": {"chapters_inserted": done_e}}
                )

            await _backfill_last_episode_at()
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "done",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            logger.info(f"[import-bundle {job_id}] done titles={done_t} eps={done_e}")
        except Exception as e:
            logger.exception(f"[import-bundle {job_id}] failed")
            await db.system_logs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

    asyncio.create_task(_worker())
    return {
        "status": "processing",
        "job_id": job_id,
        "titles_total": len(titles),
        "episodes_total": len(episodes),
        "poll_url": "/api/admin/job-status?kind=admin_import_bundle",
    }


@api.get("/admin/import-bundle/status")
async def admin_import_bundle_status(_: dict = Depends(require_admin)):
    """Legacy status endpoint kept for backwards compat — prefer /admin/job-status."""
    log = await db.system_logs.find_one(
        {"kind": "admin_import_bundle"}, {"_id": 0}, sort=[("started_at", -1)]
    )
    if not log:
        return {"status": "idle"}
    return log



@api.get("/admin/refresh-log")
async def admin_refresh_log(_: dict = Depends(require_admin)):
    """Last 20 refresh runs (auto + manual)."""
    logs = await db.system_logs.find({"kind": {"$in": ["mangaspark_refresh", "mangaspark_refresh_manual", "olympus_refresh"]}}).sort("at", -1).limit(20).to_list(None)
    for log in logs:
        log.pop("_id", None)
    return logs

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

    # Background scheduler: refresh Arabic chapter sources every 6 hours
    async def _mangaspark_refresh_loop():
        import scrape_mangaspark
        from scrape_olympustaff import site_alive, refresh_latest as olympus_refresh
        # initial delay so app finishes startup quickly
        await asyncio.sleep(60)
        while True:
            try:
                if await site_alive("https://manga-spark.net/"):
                    stats = await scrape_mangaspark.refresh_all_chapters(db_arg=db)
                    logger.info(f"[mangaspark refresh] scanned={stats['titles_scanned']} new_chapters={stats['new_chapters']}")
                    await db.system_logs.insert_one({
                        "kind": "mangaspark_refresh",
                        "at": datetime.now(timezone.utc).isoformat(),
                        **stats,
                    })
                else:
                    logger.warning("[mangaspark refresh] site unreachable — skipped")
            except Exception as e:
                logger.exception(f"mangaspark refresh failed: {e}")
            try:
                ostats = await olympus_refresh(db, max_chapters=300)
                logger.info(f"[olympus refresh] scanned={ostats['titles_scanned']} new_chapters={ostats['new_chapters']}")
                await db.system_logs.insert_one({
                    "kind": "olympus_refresh",
                    "at": datetime.now(timezone.utc).isoformat(),
                    **ostats,
                })
            except Exception as e:
                logger.exception(f"olympus refresh failed: {e}")
            # 6 hours
            await asyncio.sleep(6 * 60 * 60)

    asyncio.create_task(_mangaspark_refresh_loop())
    logger.info("Background mangaspark refresh scheduler started (every 6h)")

    # One-time (idempotent) backfill of titles.last_episode_at for the "الجديد" sort
    async def _backfill_task():
        try:
            missing = await db.titles.count_documents({"has_chapters": {"$ne": False}, "last_episode_at": {"$exists": False}})
            if missing > 0:
                await _backfill_last_episode_at()
                logger.info(f"Backfilled last_episode_at for titles (was missing on {missing})")
        except Exception:
            logger.exception("last_episode_at backfill failed")

    asyncio.create_task(_backfill_task())

@app.on_event("shutdown")
async def on_stop():
    client.close()

@api.get("/")
async def root():
    return {"ok": True, "name": "Otaku Hub"}
