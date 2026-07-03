# KOC Season 2 — Mobile PWA (PRD)

## Original Problem Statement
Convert https://github.com/pdreddy/koc-season-2.git (static HTML + Firebase RTDB tennis tournament app) into a mobile PWA. Keep Firebase as backend (no Python). Add admin password, 16 teams with per-team passwords for score entry, and validate player names from existing rosters during scoring with fuzzy-match suggestions for mismatches.

## Architecture
- **Frontend**: React 18 + React Router v6 (CRA) as a mobile-first PWA
- **Backend**: Firebase Realtime Database (project `koc2-20fb8`) — direct client access at path `koc_s2/*`. A minimal FastAPI stub at `/app/backend/server.py` exists only to satisfy supervisor (returns `/api/health`); no business logic.
- **Service Worker / Manifest**: `public/sw.js` + `public/manifest.json` provide installability ("Add to Home Screen") on iOS/Android.
- **Auth**: Two-role local password auth stored in Firebase (`admin.password` + each `team.password`). Sessions persisted in `localStorage` (`koc_session_v1`).

## User Personas
1. **Guest** — Reads-only: Teams, Standings, Matches, Rules.
2. **Team Captain** — Logs in with team password; can enter scores for matches involving their own team.
3. **Admin** — Logs in with admin password; can manage teams (name/abbr/password/players/captain), change admin password, view all team passwords, delete individual matches or clear all results.

## Core Requirements (static)
- 16 teams, 7 players each (1 captain + 6 players).
- Score entry: 1 Singles + 2 Doubles courts; best-of-3 sets each; first-to-4 games per set; 10-pt tiebreak on 3-3.
- Player name fuzzy matching: exact ✓ (green), suggestions when similarity ≥ 0.45, auto-match at ≥ 0.92, ✗ when no candidates.
- Standings sort: Match Pts → Set Diff → Sets Won → Game Diff → Games Won.
- Top 4 highlighted as qualified.

## Implemented (2026-01)
- [x] React PWA scaffolding (CRA + service worker + manifest + iOS/Android icons)
- [x] Firebase RTDB integration with anonymous auth bootstrap + group-field migration
- [x] Auto-seeding of 16 teams split into Group A / Group B (8 each) + admin password on first run
- [x] Public pages: Teams (grouped), Standings (two group tables), Schedule, Matchups, Match History, Rules, Season 1 Archive, More
- [x] Login page with Team/Admin tabs + guest browse
- [x] Score Entry with TWO modes (Form + Quick Paste); both validate names against rosters with fuzzy match
- [x] Validation prevents save when any player name doesn't match team roster; aggregated error messages
- [x] Admin dashboard: Teams editor, **Schedule editor** (per-fixture group/round/date/time/teams/status with Regenerate/Add/Clear-all tools), Settings (admin password + clear-all-matches), Passwords
- [x] Match deletion & clear-all (admin only)
- [x] Group A / Group B split (intra-group standings only); admin can move teams between groups
- [x] Side-by-side Group A | Group B layout on Teams & Standings pages
- [x] Match records store team IDs (`t1Id`/`t2Id`/`winnerId`) → renames don't break history (via `src/utils/matchTeams.js`)
- [x] **Schedule moved to Firebase** (`koc_s2/schedule`) — auto-seeded round-robin: 56 fixtures (2 groups × 7 rounds × 4 matches), Sundays starting July 5, 2026 (first Sunday on/after June 30, 2026). Admin-editable per match.
- [x] **Season 1 Archive page** (`/season1`) reads read-only from Firebase path `KOC2DBPONEW` — shows final standings (gold/silver/bronze medals top 3) and full match history with details
- [x] Matchups page (Player Stats / Singles Cap / Doubles partnerships) with caps tracking
- [x] Mobile-first layout: sticky header, fixed 5-tab bottom-nav, safe-area-inset support
- [x] localStorage session persistence

## Backlog / Future (P1/P2)
- P2: Tighten Firebase RTDB security rules + enable anonymous auth for production.
- P2: Hash team/admin passwords (currently plaintext in RTDB).
- P3: Refactor 556-line ScoreEntry.js into Form + QuickEntry separate modules.
- P3: Push notifications for new results / match-day reminders.
- P3: CSV export of standings / per-team stats.
- P2: Session TTL for shared captain devices.
- P2: Hash team/admin passwords (currently plaintext in RTDB).
- P2: Push notifications for new results.
- P2: CSV export of standings / per-team stats.

## Test Credentials
See `/app/memory/test_credentials.md`. Admin: `KOCPO#ADMIN`. Team pattern: `KOC<ABBR>#2` (e.g., SK → `KOCSK#2`).

## Files / Structure
```
/app/frontend/        React PWA (yarn start on port 3000)
  src/firebase.js     Firebase config + RTDB paths
  src/data/initialTeams.js   Seed: 9 real teams + 7 placeholders
  src/utils/nameMatch.js     Levenshtein-based fuzzy matcher
  src/contexts/AuthContext.js  localStorage session
  src/pages/{Teams,Standings,History,Rules,Login,Admin,ScoreEntry}.js
  src/components/{Header,BottomNav}.js
/app/backend/         FastAPI stub (no business logic)
/app/legacy/          Original static HTML files (for reference)
```
