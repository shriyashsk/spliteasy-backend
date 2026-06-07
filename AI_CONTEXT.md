# AI_CONTEXT.md — SplitEasy (Splitwise Clone)

> **Single source of truth for the entire project.**
> This file contains the full working context used to generate the app.
> The AI (Claude Sonnet 4.6, claude.ai) continuously updated this file throughout the build.
> Any developer or AI agent must be able to read this file alone and rebuild a functionally equivalent app.
> Another evaluator should be able to paste this into Claude and recreate a similar codebase.

---

## 1. Product Understanding

### What Problem This Solves
When groups of people share expenses — on trips, in shared apartments, between friends — tracking who paid for what and who owes whom becomes chaotic. People lose track, forget, and awkward conversations happen. Splitwise solved this, but left a critical gap: the payment disconnect. You see what you owe, but then you have to leave the app, open a separate payment app, send the money, and come back to manually mark it settled.

SplitEasy fixes this end-to-end. It tracks shared expenses with flexible split types, calculates pairwise net balances across groups, and closes the loop — letting users settle up or record a payment without leaving the app, including a UPI deeplink flow on mobile so the entire journey is one screen.

### Core Product Values
- **Accuracy** — Balance calculations must be mathematically correct. Every edit, delete, and settlement must recalculate affected balances transactionally.
- **Transparency** — Net balances must show the contributing expenses and amounts. Users should never wonder "why do I owe this?"
- **Flexibility** — Four split methods to match how people actually split things in real life.
- **Real-time** — Expense comments and balance updates must reflect instantly across all users in a group.
- **Closure** — The settle-up flow completes without leaving the app.

### Splitwise Research — What I Observed
1. Groups are named with a category (trip, home, couple, other) and a cover image. Members are invited by email.
2. Expenses have one payer, a total amount, and are split among participants. Split methods: equal, unequal (custom amounts), percentage, shares.
3. Balances are shown as pairwise net amounts — not per-expense debt. "You owe Arjun ₹340 in Goa Trip."
4. The individual dashboard shows a cross-group net position. "Overall you owe ₹800."
5. Settle up records a payment between two users and reduces the balance.
6. Expense-level comments allow discussion within the context of each expense.
7. Editing or deleting an expense recalculates all affected balances.
8. Removing a member preserves their historical data — they just can't be added to new expenses.

### Product Assumptions Made
- One payer per expense. Co-payers not supported.
- No debt simplification (A owes B who owes C is NOT simplified to A owes C). Raw pairwise balances shown.
- Invites via email link only. No phone number search or username lookup.
- No receipt scanning, bank linking, or recurring expenses.
- Responsive web app only — no native mobile app.
- PostgreSQL required (relational DB only per assignment).
- No ghost/placeholder users — invite flow uses a pending invite table.

---

## 2. User Personas

| Persona | Description | Primary Need |
|---|---|---|
| **Organizer Olivia** | Creates groups, invites members, logs most expenses | Fast expense entry, clear group overview, working invite flow |
| **Participant Priya** | Checks what she owes, confirms splits, settles up | Dashboard net balance, one-tap settle up |
| **Power Member Arjun** | Edits expenses post-facto, reviews splits carefully | Split breakdown display, edit history, balance recalc transparency |
| **Disputer Dev** | Questions an expense edit — "why did my balance change?" | Before/after edit log, activity feed per group |

---

## 3. Product Scope

### MVP — Shipped

| # | Feature | Status |
|---|---|---|
| 1 | Email + password signup / login | ✓ Shipped |
| 2 | Google OAuth login | ✓ Shipped |
| 3 | Forgot password / reset via email | ✓ Shipped |
| 4 | Change password from profile | ✓ Shipped |
| 5 | Create and manage groups | ✓ Shipped |
| 6 | Invite members by email link | ✓ Shipped |
| 7 | Add / remove members | ✓ Shipped |
| 8 | Add expenses — equal split | ✓ Shipped |
| 9 | Add expenses — unequal split | ✓ Shipped |
| 10 | Add expenses — percentage split | ✓ Shipped |
| 11 | Add expenses — shares split | ✓ Shipped |
| 12 | Pairwise balance tracking | ✓ Shipped |
| 13 | Group-wise balance view | ✓ Shipped |
| 14 | Individual balance summary dashboard | ✓ Shipped |
| 15 | Settle debts / record payments | ✓ Shipped |
| 16 | User chat in an expense (real-time) | ✓ Shipped |
| 17 | Real-time balance updates | ✓ Shipped |
| 18 | Edit log with JSONB before/after | ✓ Shipped |
| 19 | Activity feed per group | ✓ Shipped |
| 20 | Soft deletes | ✓ Shipped |
| 21 | Personalized dashboard | ✓ Shipped |
| 22 | Responsive web UI | ✓ Shipped |
| 23 | User profile | ✓ Shipped |

### Explicitly Out of Scope
- Receipt scanning / OCR
- Bank account linking or automatic payment processing
- Phone number / OTP verification
- Recurring expenses
- Debt simplification across 3+ users
- Push notifications
- Bulk expense import / CSV export
- Native mobile app
- Multi-payer per expense
- Split by item (itemised receipt splits)
- Redis
- Multi-group debt netting

---

## 4. Core Business Rules

1. New group members do not inherit past expenses — they track from join date only.
2. Settlement amount cannot exceed current net owed amount. UI validates and caps input.
3. Only group admin (creator) can remove members. Any member can edit or delete any expense.
4. Removed members' historical data (expenses, balance contributions) remains. They no longer appear in new expense split selectors.
5. Expense edits fully recalculate affected balances transactionally. An `edit_log` row (before/after JSON) is written in the same transaction.
6. Debt simplification is NOT implemented — raw pairwise balances shown with per-expense breakdown.
7. All four split types reduce to a `(user_id, amount)` list stored in `expense_splits`. Original `percentage` and `share_count` inputs are preserved for display.
8. `user_id_1` in the `balances` table is always the lexicographically smaller UUID. Prevents duplicate rows for the same pair.
9. Split rounding remainder on non-divisible amounts is assigned to the payer.
10. One payer per expense. Co-payers out of scope.
11. Invite flow uses a pending `invites` table — no ghost/placeholder users ever created.
12. A user can belong to multiple groups simultaneously.
13. Deleting an expense sets `deleted_at` (soft delete) and reverses its balance contribution.

---

## 5. Authentication Design

| Decision | Choice | Reasoning |
|---|---|---|
| Auth methods | Email + password AND Google OAuth | OAuth reduces signup friction |
| Session type | Server-side sessions in PostgreSQL `sessions` table | Sessions can be revoked; JWTs cannot be invalidated without extra infrastructure |
| Token storage | `localStorage` (frontend) | Acceptable for assignment scope |
| Session persistence | Persistent — survives browser refresh | Silently extended on activity |
| Forced logout | `revoked_at` set on session row | Immediate invalidation |
| Forgot password | Email link with one-time reset token | Via SendGrid |
| Password change | Current + new; authenticated endpoint | — |
| Google-only users | `password_hash` is null; `oauth_provider_id` holds Google sub ID | — |

---

## 6. Database Schema

> All tables use PostgreSQL. Relational DB only per assignment requirement.

### Table: `users`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
full_name           VARCHAR(255) NOT NULL
email               VARCHAR(255) UNIQUE NOT NULL
password_hash       VARCHAR(255)
auth_provider       VARCHAR(50) DEFAULT 'email'
oauth_provider_id   VARCHAR(255)
email_verified      BOOLEAN DEFAULT FALSE
preferred_currency  VARCHAR(10) DEFAULT 'USD'
avatar_url          TEXT
timezone            VARCHAR(100)
status              VARCHAR(50) DEFAULT 'active'
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ DEFAULT NOW()
last_login_at       TIMESTAMPTZ
deleted_at          TIMESTAMPTZ
```

### Table: `sessions`
```sql
session_id      VARCHAR(255) PRIMARY KEY
user_id         UUID REFERENCES users(id)
created_at      TIMESTAMPTZ DEFAULT NOW()
expires_at      TIMESTAMPTZ NOT NULL
revoked_at      TIMESTAMPTZ
user_agent      TEXT
ip_address      VARCHAR(100)
```

### Table: `groups`
```sql
id                        UUID PRIMARY KEY DEFAULT gen_random_uuid()
name                      VARCHAR(255) NOT NULL
created_by_user_id        UUID REFERENCES users(id)
currency                  VARCHAR(10) DEFAULT 'USD'
description               TEXT
cover_image_url           TEXT
group_icon                TEXT
category                  VARCHAR(50)
default_split_preference  VARCHAR(50)
status                    VARCHAR(50) DEFAULT 'active'
archived_at               TIMESTAMPTZ
created_at                TIMESTAMPTZ DEFAULT NOW()
updated_at                TIMESTAMPTZ DEFAULT NOW()
```

### Table: `group_members`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
group_id            UUID REFERENCES groups(id)
user_id             UUID REFERENCES users(id)
invited_by_user_id  UUID REFERENCES users(id)
role                VARCHAR(50) DEFAULT 'member'
joined_at           TIMESTAMPTZ DEFAULT NOW()
removed_at          TIMESTAMPTZ
UNIQUE(group_id, user_id)
```

### Table: `expenses`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
group_id            UUID REFERENCES groups(id)
title               VARCHAR(255) NOT NULL
description         TEXT
category            VARCHAR(100)
amount              NUMERIC(12, 2) NOT NULL
currency            VARCHAR(10) NOT NULL
paid_by_user_id     UUID REFERENCES users(id)
created_by_user_id  UUID REFERENCES users(id)
split_type          VARCHAR(50) NOT NULL
expense_date        DATE DEFAULT CURRENT_DATE
status              VARCHAR(50) DEFAULT 'active'
note                TEXT
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ DEFAULT NOW()
deleted_at          TIMESTAMPTZ
```

### Table: `expense_splits`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
expense_id      UUID REFERENCES expenses(id)
user_id         UUID REFERENCES users(id)
amount          NUMERIC(12, 2) NOT NULL
percentage      NUMERIC(5, 2)
share_count     INTEGER
exchange_rate   NUMERIC(18, 6)
is_settled      BOOLEAN DEFAULT FALSE
settled_at      TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT NOW()
updated_at      TIMESTAMPTZ DEFAULT NOW()
```

### Table: `balances`
```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
group_id        UUID REFERENCES groups(id)
user_id_1       UUID REFERENCES users(id)   -- always lexicographically SMALLER UUID
user_id_2       UUID REFERENCES users(id)   -- always lexicographically LARGER UUID
net_amount      NUMERIC(12, 2) NOT NULL     -- positive = user_1 is owed by user_2
currency        VARCHAR(10) NOT NULL
last_updated_at TIMESTAMPTZ DEFAULT NOW()
UNIQUE(group_id, user_id_1, user_id_2)
```

### Table: `settlements`
```sql
id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()
group_id              UUID REFERENCES groups(id)
paid_by_user_id       UUID REFERENCES users(id)
paid_to_user_id       UUID REFERENCES users(id)
amount                NUMERIC(12, 2) NOT NULL
currency              VARCHAR(10) NOT NULL
note                  TEXT
upi_transaction_ref   VARCHAR(255)
status                VARCHAR(50) DEFAULT 'confirmed'
settlement_date       DATE DEFAULT CURRENT_DATE
created_at            TIMESTAMPTZ DEFAULT NOW()
deleted_at            TIMESTAMPTZ
```

### Table: `edit_logs`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
entity_type         VARCHAR(100) NOT NULL
entity_id           UUID NOT NULL
changed_by_user_id  UUID REFERENCES users(id)
change_type         VARCHAR(50) NOT NULL
before_json         JSONB
after_json          JSONB
created_at          TIMESTAMPTZ DEFAULT NOW()
```

### Table: `invites`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
token               VARCHAR(255) UNIQUE NOT NULL
group_id            UUID REFERENCES groups(id)
invited_email       VARCHAR(255) NOT NULL
invited_by_user_id  UUID REFERENCES users(id)
status              VARCHAR(50) DEFAULT 'pending'
accepted_by_user_id UUID REFERENCES users(id)
accepted_at         TIMESTAMPTZ
expires_at          TIMESTAMPTZ NOT NULL
created_at          TIMESTAMPTZ DEFAULT NOW()
```

### Table: `expense_comments`
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
expense_id  UUID REFERENCES expenses(id)
user_id     UUID REFERENCES users(id)
content     TEXT NOT NULL
created_at  TIMESTAMPTZ DEFAULT NOW()
updated_at  TIMESTAMPTZ DEFAULT NOW()
```

---

## 7. Balance Calculation Logic

**Strategy: Running totals cache** — the `balances` table is updated transactionally on every write. Reads are O(1).

**Convention:** `user_id_1 < user_id_2` always (lexicographic). Positive `net_amount` = user_1 is owed by user_2.

**When balances recalculate:**
- New expense created → apply splits to balances
- Expense edited → reverse old splits, apply new splits (same transaction)
- Expense deleted → reverse splits
- Settlement recorded → reduce balance by settlement amount
- Settlement reversed → restore balance

---

## 8. Tech Stack

| Layer | Technology | Decision Reason |
|---|---|---|
| Frontend framework | React + Vite | SPA sufficient; Vite is faster than CRA |
| UI state | Zustand | Lightweight; separates UI state from server state |
| Server state | React Query (TanStack v5) | Handles fetching, caching, invalidation |
| Styling | Tailwind CSS v3 (plain, no shadcn) | shadcn dropped due to jsconfig/tsconfig conflict with Vite JS project |
| Routing | React Router v6 | Standard for React SPA |
| Real-time | Socket.io client + python-socketio | WebSocket-only; required for expense chat |
| Backend | Python 3.11 + FastAPI | Async; auto-generated docs at `/docs` |
| ORM | SQLAlchemy (async) + Alembic | Standard Python ORM + migration management |
| Auth sessions | PostgreSQL `sessions` table | Revocable; JWTs cannot be invalidated without Redis |
| OAuth | Google OAuth 2.0 | Handled backend-side |
| Email | SendGrid free tier | Invite emails + password reset |
| Database | PostgreSQL | Relational; required by assignment |
| Frontend deploy | Vercel | Auto-deploys from GitHub main |
| Backend deploy | Railway | FastAPI service + PostgreSQL in one project |
| AI Tool | **Claude (claude.ai) — Claude Sonnet 4.6** | Primary development collaborator |

---

## 9. API Design

**Base URL:** `https://spliteasy-backend-production.up.railway.app`
**Auth header:** `Authorization: Bearer {session_token}` on all protected routes.

### Auth Routes
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | Public | Register; returns session token |
| POST | `/auth/login` | Public | Login; returns session token |
| POST | `/auth/logout` | Protected | Revokes session |
| GET | `/auth/me` | Protected | Returns current user |
| GET | `/auth/google` | Public | Redirects to Google OAuth |
| GET | `/auth/google/callback` | Public | Handles OAuth; issues session |
| POST | `/auth/forgot-password` | Public | Sends reset email |
| POST | `/auth/reset-password` | Public | Validates token; sets new password |
| POST | `/auth/change-password` | Protected | Sets new password |

### Group Routes
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/groups` | Protected | All groups for current user |
| POST | `/groups` | Protected | Create group |
| GET | `/groups/:id` | Protected | Group detail + members |
| DELETE | `/groups/:id/members/:userId` | Protected (admin) | Soft-remove member |
| GET | `/groups/:id/balances` | Protected | Pairwise net balances |
| GET | `/groups/:id/expenses` | Protected | Paginated expense list |
| POST | `/groups/:id/expenses` | Protected | Create expense |
| GET | `/groups/:id/settlements` | Protected | Settlement history |
| POST | `/groups/:id/settlements` | Protected | Record settlement |
| GET | `/groups/:id/activity` | Protected | Activity feed |
| POST | `/groups/:id/invites` | Protected | Send invite email |

### Expense Routes
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/expenses/:id` | Protected | Expense detail + splits |
| PUT | `/expenses/:id` | Protected | Edit expense; recalculates balances |
| DELETE | `/expenses/:id` | Protected | Soft-delete; reverses balance |
| GET | `/expenses/:id/comments` | Protected | All comments |
| POST | `/expenses/:id/comments` | Protected | Post comment; emits `comment:new` |

### Settlement Routes
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/settlements/:id/reverse` | Protected | Reverse settlement |

### Invite Routes
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/invites/:token` | Public | Validate token |
| POST | `/invites/:token/accept` | Protected | Accept invite; join group |

### User Routes
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | Protected | Get profile |
| PUT | `/users/me` | Protected | Update profile |
| GET | `/users/me/balances` | Protected | Cross-group balance summary |

### WebSocket
| | Value |
|---|---|
| Connection path | `WS /socket.io` |
| Auth | `{ auth: { token: session_token } }` in handshake |
| Event: balance updated | `balance:updated` → room `group:{group_id}` |
| Event: new comment | `comment:new` → room `expense:{expense_id}` |

### Standard Response Format
```json
{ "success": true, "data": { ... } }
{ "success": false, "error": { "code": "...", "message": "..." } }
```

---

## 10. Frontend Structure

```
src/
├── pages/
│   ├── LoginPage.jsx
│   ├── SignupPage.jsx
│   ├── DashboardPage.jsx
│   ├── GroupDetailPage.jsx
│   ├── ExpenseDetailPage.jsx
│   ├── ProfilePage.jsx
│   ├── InvitePage.jsx
│   ├── ForgotPasswordPage.jsx
│   ├── ResetPasswordPage.jsx
│   └── AuthCallbackPage.jsx
├── components/
│   ├── layout/
│   │   ├── Navbar.jsx
│   │   ├── BottomNav.jsx
│   │   └── ProtectedRoute.jsx
│   ├── groups/
│   ├── expenses/
│   ├── settlements/
│   └── comments/
├── providers/
│   └── SocketProvider.jsx
├── store/
│   └── authStore.js        (Zustand — token + user from localStorage)
├── hooks/
│   ├── useGroups.js
│   ├── useExpenses.js
│   └── useBalances.js
└── api/
    ├── axiosInstance.js    (Bearer token interceptor; 401 redirect)
    ├── auth.js
    ├── groups.js
    ├── expenses.js
    └── settlements.js
```

**State strategy:** Zustand holds auth state only. All server data lives in React Query. Socket.io events call `queryClient.invalidateQueries(...)`.

**Routing:** React Router v6. `vercel.json` added with rewrite rule to fix 404 on direct URL access.

---

## 11. Deployment

### Backend (Railway)
- Service: `spliteasy-backend` connected to GitHub repo
- PostgreSQL plugin in same Railway project
- Start command: `alembic upgrade head && uvicorn app.main:socket_app --host 0.0.0.0 --port $PORT`
- Port exposed: 8080
- Python version: 3.11.9 (enforced via `runtime.txt`)
- `mise.toml` added with `python.github_attestations = false`
- All env vars set in Railway Variables dashboard
- Live URL: `https://spliteasy-backend-production.up.railway.app`

### Frontend (Vercel)
- Connected to `spliteasy-frontend` GitHub repo
- Build: `npm run build` | Output: `dist`
- Auto-deploys on every push to `main`
- `vercel.json` added for React Router SPA routing
- Env vars: `VITE_API_BASE_URL` and `VITE_SOCKET_URL` both pointing to Railway URL
- Live URL: `https://spliteasy-frontend.vercel.app`

### Google OAuth
- Redirect URIs configured:
  - `http://localhost:8000/auth/google/callback`
  - `https://spliteasy-backend-production.up.railway.app/auth/google/callback`

---

## 12. Environment Variables

### Backend (Railway)
```
DATABASE_URL=postgresql+asyncpg://...
SESSION_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SENDGRID_API_KEY=...
FROM_EMAIL=...
EXCHANGE_RATE_API_KEY=...
FRONTEND_URL=https://spliteasy-frontend.vercel.app
BACKEND_URL=https://spliteasy-backend-production.up.railway.app
CORS_ORIGINS=https://spliteasy-frontend.vercel.app
```

### Frontend (Vercel)
```
VITE_API_BASE_URL=https://spliteasy-backend-production.up.railway.app
VITE_SOCKET_URL=https://spliteasy-backend-production.up.railway.app
```

---

## 13. Known Limitations

- No debt simplification — raw pairwise balances only
- No receipt scanning
- No UPI deeplink on mobile (settlement is record-only)
- No settlement reversal UI (endpoint exists, no frontend component)
- No rate limiting on API endpoints
- Session token in localStorage (httpOnly cookie would be more secure)
- No email verification required at signup
- No pagination UI on members or settlements lists

---

## 14. Changes Made During Implementation

| Date | Section | What Changed | Reason |
|---|---|---|---|
| Day 0 | Schema | `TIMESTAMPTZ` replaced with `DateTime(timezone=True)` | asyncpg rejects offset-naive datetimes |
| Day 0 | Auth | Switched from JWT to DB sessions | Session revocability discussion |
| Day 0 | Stack | Added `python-socketio` | Real-time expense chat requirement |
| Day 1 | Deploy | `bcrypt` pinned to `4.0.1` | passlib incompatible with bcrypt 4.2.0 |
| Day 1 | Deploy | `asyncpg` upgraded to `0.30.0` | Python 3.11 pre-built wheel availability on Railway |
| Day 1 | Deploy | `runtime.txt` added with `python-3.11.9` | Railway defaulted to Python 3.13; asyncpg build failed |
| Day 1 | Deploy | `mise.toml` added | Railway mise tool failed GitHub artifact attestation for Python |
| Day 1 | Deploy | Port set to 8080 | Railway auto-assigned 8080; domain generated for that port |
| Day 2 | Frontend | shadcn dropped entirely | jsconfig/tsconfig conflict; shadcn init kept failing on Vite JS project |
| Day 2 | Frontend | Plain Tailwind CSS used for all components | shadcn not needed; all UI built with Tailwind utility classes |
| Day 2 | Frontend | `vercel.json` added | React Router routes returning 404 on Vercel direct URL access |
| Day 2 | Frontend | `axiosInstance` 401 interceptor skips /login and /signup | Caused redirect loop on auth pages |
| Day 2 | Frontend | `ProfilePage` fix — `updateUser({ ...user, ...form })` | Backend PUT `/users/me` returns `{message}` not user object; was overwriting user in localStorage and breaking `user.id` |
| Day 2 | Balance service | Fixed sign logic for user_id ordering | Bug where A→B balance showed as negative |
| Day 2 | Split service | Added Decimal precision | Float rounding caused incorrect split amounts |

---

## 15. Q&A Log (Key Prompts and Decisions)

**AI:** Is this primarily a tracking tool, a payment tool, or both?
**Me:** Both — and the payment disconnect is the core UX failure to fix.
**→ Impact:** UPI deeplink settle-up flow added; `upi_transaction_ref` on settlements.

---

**AI:** JWT or server-side sessions? What do you want to happen if a user's phone is stolen?
**Me:** Server-side sessions so I can revoke immediately — JWT doesn't work here.
**→ Impact:** Replaced JWT entirely with `sessions` table; `revoked_at` field.

---

**AI:** Should balances be computed on-the-fly or maintained as running totals?
**Me:** Running totals — optimise for read speed, accept write complexity.
**→ Impact:** Added `balances` table; `balance_service.py` with upsert logic.

---

**AI:** When a member is removed, what happens to their historical balance contributions?
**Me:** Preserved — audit integrity requires history to stay.
**→ Impact:** `removed_at` soft removal; historical balance contributions kept.

---

**AI:** For real-time — polling, SSE, or WebSocket?
**Me:** WebSocket via Socket.io.
**→ Impact:** `python-socketio` backend; `SocketProvider` frontend; two event types.

---

**AI:** Where are you deploying?
**Me:** Vercel for frontend, Railway for backend.
**→ Impact:** Deployment documented for both. Start command set to uvicorn.

---

## 16. How AI_CONTEXT.md Was Maintained

- Before any code: Claude asked all questions first. After every answered question, Claude updated the relevant section of AI_CONTEXT.md.
- During the build: whenever a decision changed, Claude updated the relevant section and added a row to the Implementation Change Log.
- Schema changes triggered an update to Section 6 before any model code was written.
- AI_CONTEXT.md was committed to the repository on every meaningful change.

