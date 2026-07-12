# Otaku Hub — PRD

## Problem Statement (original)
> اريده تطبيق للانمي و مانهوا و المانجا و ايضا اريده ان يحتوي على وسيلة للدرشاشة العامة و الخاصه للمناقشات و للصداقة

## Architecture
- **Backend**: FastAPI + Motor (MongoDB) — UUID ids, all routes prefixed with `/api`
- **Frontend**: React 19 + react-router 7 + Tailwind + shadcn/ui (RTL Arabic interface)
- **Auth**: JWT (email/password, bcrypt). Token in localStorage.
- **Chat realtime**: polling (3s) — simple, no WebSocket complexity
- **Theme**: dark cinematic (#050505 / #0F111A / #E63946 crimson + #FFB703 gold) with Kufam + Cairo Arabic fonts

## Core Requirements
- Catalog of anime / manhwa / manga (admin-managed)
- Per-title discussion rooms + public lobby + private DMs
- Friends system with request/accept/reject
- Watchlist (5 statuses) + Reviews/Ratings
- Notifications bell

## Implemented (May 2026)
- ✅ JWT auth: register / login / me / update profile
- ✅ Titles catalog (search + filter by type), title detail, reviews, ratings (avg)
- ✅ Watchlist (watching/completed/plan/dropped/favorite)
- ✅ Friends system (search, request, accept, reject, remove)
- ✅ Chat rooms: lobby, per-title, DMs (polling, 3s)
- ✅ Notifications (friend requests / accepted / new DM) with unread bell + dropdown
- ✅ Admin panel: add/delete titles, manage episodes/chapters per title
- ✅ Episodes (anime) with embedded video player + Chapters (manga/manhwa) with image-page reader, prev/next navigation
- ✅ Seed admin (admin@otaku.com / Admin@12345) + 6 sample titles + 72 episodes/chapters
- ✅ RTL Arabic UI with Kufam display font + Cairo body font
- ✅ data-testid on all interactive elements
- ✅ **MangaDex API integration** (Feb 2026): auto-import 1,200+ titles, backend image proxy, language-separated chapters (AR/EN)
- ✅ **Catalog pagination** (Feb 2026): 30 items/page, page selector, total count display
- ✅ **Bilingual UI toggle** (Feb 2026): Arabic/English site language in Settings (`/api/auth/me` PATCH stores `locale`, document `dir` switches RTL/LTR reactively via Layout)
- ✅ **Profile cover image** (Feb 2026): user-selectable background URL or preset, rendered as banner on `/profile`
- ✅ **`/settings` route** (Feb 2026): registered in App.js (was missing)
- ✅ **Image uploads via GridFS** (Feb 2026): `POST /api/uploads/image` accepts multipart files (PNG/JPEG/WebP/GIF, max 5MB), stores in MongoDB GridFS, served via `GET /api/uploads/{id}` with long-cache. Settings page exposes "Upload from device" buttons for avatar and profile background alongside URL paste.
- ✅ **Proxy whitelist fix** (Jun 2026): Chapter images for newer manga-spark titles (e.g., Return of the Mount Hua Sect) were hosted on additional CDN subdomains (`leksparkio`, `s2/s4/s5/s6/s7/s8/ssparkio/tempsparkio.manga-spark.com`) which the `/api/proxy/image` whitelist rejected (400). Whitelist relaxed to any `manga-spark.com`/`manga-spark.net` host. Verified all 10,623 mangaspark episodes have pages and reader loads images. NOTE: user must REDEPLOY for production to get the fix.
- ✅ **MangaSpark scraper** (Feb 2026): `backend/scrape_mangaspark.py` imports popular Arabic manhwa from manga-spark.net. **122 titles + 2,301 chapters** imported with full Arabic chapter images. Backend image proxy extended with browser UA + Referer headers to bypass Cloudflare on `s3sparkio.manga-spark.com`. Re-runnable safely (skips already-imported titles). Grand total catalog: 3,876 titles.
- ✅ **Deployment fix** (Feb 2026): Added missing `refresh_all_chapters()` function in `scrape_mangaspark.py` (caused ImportError on startup). Removed hardcoded `mongodb://localhost:27017` from `scrape_mangaspark.py` and `scrape_mangadex.py` — now use `MONGO_URL` / `DB_NAME` env vars for Atlas compatibility.
- ✅ **Public browsing (optional auth)** (Feb 2026): Added `optional_user` dependency. Removed auth from `GET /api/episodes/{eid}/pages` and `GET /api/titles/{tid}/episodes/{eid}`. Frontend Layout hides messages/friends nav and shows "تسجيل الدخول" button for guests. Reusable `LoginGate` component wraps chat (`ChatRoom`), reviews submit form, and lobby. Verified by testing agent 100%.
- ✅ **Continue Reading** (Feb 2026): New endpoints `POST /api/reading/progress`, `GET /api/reading/continue`, `GET /api/reading/progress/{title_id}` (upsert by user_id+title_id). `EpisodeView` writes server-side progress for logged-in users and falls back to `localStorage` (`reading:<title_id>`) for guests. `Home` shows horizontal "تابع القراءة" rail; `TitleDetail` shows a continue button. Works for guests AND logged-in.
- ✅ **PWA + Play Store prep** (Feb 2026): `public/manifest.json` (name, icons 192/512, standalone, RTL), `public/service-worker.js` (network-first navigation, cache-first static, skip API), theme-color + apple-touch-icon meta tags in `index.html`. SW registered on window load. Static `/privacy` and `/terms` legal pages added (required for Play Store submission). Footer in Layout links to both.

## Backlog
- P1: Emergent-managed Google OAuth (deferred per first-iteration scope)
- P1: WebSocket-based realtime chat (currently 3s polling)
- P2: Threaded review replies
- P2: Push notifications when a favorited title gets a new chapter
- P2: Search across reviews and discussions
- P2: Extend i18n dictionary to cover Lobby, DM, Friends, Admin, TitleDetail full strings
- P2: Fallback poster for ContinueReading card when CDN image fails (testing agent suggestion)
- P3: Move `@api.get('/')` above `app.include_router(api)` — pre-existing cosmetic 404 on root (no functional impact)
- ✅ **UI updates trio** (Jun 2026): (1) X remove button on "تابع القراءة" cards — `DELETE /api/reading/progress/{title_id}` for users, localStorage removal for guests. (2) "الجديد (فصول حديثة)" sort option — `sort_by=updated` sorts by new `titles.last_episode_at` field (maintained on every episode insert in server.py + both scrapers; idempotent startup backfill `_backfill_last_episode_at()` also runs after bundle import, so production self-heals on deploy). (3) "مانها" (manhua) type — new Home tab, TitleCard/i18n labels, admin add-title option, MangaDex scraper auto-classifies by originalLanguage (ja/ko/zh), and new admin background job `POST /api/admin/reclassify-types` (poll kind=admin_reclassify_types) with progress card in Admin.jsx — reclassified 12 manhua in preview; user must click "تصنيف المانها" button in production after deploy.
