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

## Backlog
- P0: None — MVP complete
- P1: Emergent-managed Google OAuth (deferred per first-iteration scope)
- P1: WebSocket-based realtime chat (currently 3s polling)
- P2: Episode/chapter progress tracking per user
- P2: Threaded review replies
- P2: Image uploads for avatars (currently URL-only)
- P2: Push notifications (browser)
- P2: Search across reviews and discussions
