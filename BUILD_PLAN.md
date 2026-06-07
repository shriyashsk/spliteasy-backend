# BUILD_PLAN.md — SplitEasy (Splitwise Clone)

> **2-day implementation plan.**
> AI tool used: **Claude (claude.ai) — Claude Sonnet 4.6**
> All decisions referenced here are fully documented in `AI_CONTEXT.md`.

---

## Part 1 — Product Research

### How I Studied Splitwise

1. Created a real Splitwise account and set up two test groups: one simulating roommates (recurring expenses), one simulating a trip (one-time expenses with multiple split types).
2. Logged expenses using all four split methods — equal, unequal custom amounts, percentage, and shares — to observe how balances updated with each.
3. Tested edge cases deliberately: editing an expense after a settlement had been recorded, removing a member who still had an outstanding balance.
4. Observed the full settle-up flow: noted the step where you have to leave the app, open GPay/PhonePe separately, transfer money, return, and manually mark settled. This became the core UX problem to fix.
5. Read Splitwise's support documentation to understand feature boundaries — especially around debt simplification, currency handling, and member removal behaviour.
6. Compared with Tricount and Settle Up to identify what Splitwise does uniquely: the per-expense comment thread, the cross-group individual balance summary, and the group category system.

### What I Learned

- **Balance calculation is the hardest correctness problem.** Every expense edit, soft-delete, and settlement must recalculate pairwise balances transactionally.
- **Splitwise shows net balances, not per-expense debt.** "Priya owes you ₹340" is the sum across all expenses in the group — requires running totals, not on-the-fly computation.
- **The payment disconnect is the biggest UX failure.** Users know what they owe but must leave the app to pay, then return to record it manually.
- **Expense-level comments are underrated.** Without context, disputes happen over WhatsApp and the expense data becomes untrusted.
- **Invite flow determines adoption.** If adding someone to a group takes more than 30 seconds, the organiser gives up.
- **Split rounding is a real edge case.** ₹10 split equally between 3 people is ₹3.33, ₹3.33, ₹3.34. Someone must absorb the extra ₹0.01. This must be handled explicitly.

### Core Workflows Identified

1. **Onboarding:** Sign up → create group → invite members by email link → members accept → group is live
2. **Expense logging:** Choose group → add expense → set payer → choose split type → review per-person amounts → submit → balances update
3. **Balance viewing:** Group page → see pairwise balances → view settlement history
4. **Individual summary:** Dashboard → net position across all groups in one card
5. **Settle up:** Select who to settle with → enter amount → record → balance reduces
6. **Expense correction:** Delete expense → old balance contribution reversed → new balance applied → edit log written
7. **Expense discussion:** Open expense → post comment → other group members see it instantly via Socket.io

### Product Assumptions Made

- One payer per expense. Co-payers excluded.
- No debt simplification. Raw pairwise balances shown.
- Invites by email link only.
- No receipt scanning, bank linking, or recurring expenses.
- Responsive web app only.
- PostgreSQL required (assignment constraint).
- No ghost/placeholder users — invite flow uses a pending `invites` table.

---

## Part 2 — Architecture

### Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Frontend | React + Vite | SPA sufficient; Vite significantly faster than CRA |
| UI State | Zustand | Lightweight; keeps auth state separate from server state |
| Server State | React Query (TanStack v5) | Handles fetch/cache/invalidation; Socket.io events call `invalidateQueries` |
| Styling | Tailwind CSS v3 (plain) | shadcn dropped due to jsconfig/tsconfig conflict with Vite JS project |
| Routing | React Router v6 | Standard for React SPA |
| Real-time | Socket.io + python-socketio | Required for expense chat; WebSocket-only mode |
| Backend | Python 3.11 + FastAPI | Async; auto-generated `/docs`; fast to iterate |
| ORM | SQLAlchemy (async) + Alembic | Standard Python ORM + reproducible schema migrations |
| Auth | PostgreSQL `sessions` table | Server-side sessions are revocable; JWT cannot be invalidated without extra infra |
| OAuth | Google OAuth 2.0 | Reduces signup friction; handled backend-side |
| Email | SendGrid free tier | Invite emails + password reset |
| Database | PostgreSQL | Relational; required by assignment |
| Frontend Deploy | Vercel | One-command import; auto-deploys from GitHub |
| Backend Deploy | Railway | Hosts FastAPI + PostgreSQL in one project |
| AI Tool | Claude (claude.ai) — Claude Sonnet 4.6 | Primary development collaborator |

### Database Schema

11 tables. Full DDL in `AI_CONTEXT.md §6`.

| Table | Purpose |
|---|---|
| `users` | Accounts; email/password and Google OAuth |
| `sessions` | Server-side sessions with `revoked_at` |
| `groups` | Named groups with category and split preference |
| `group_members` | Membership with `removed_at` soft removal |
| `expenses` | Expense records with split type and payer |
| `expense_splits` | Per-user resolved amounts; stores original % and share_count |
| `balances` | Pairwise running total cache; `user_id_1 < user_id_2` convention |
| `settlements` | Payment records; reversible |
| `edit_logs` | JSONB before/after diff on every change |
| `invites` | Token-based pending invites; 7-day expiry |
| `expense_comments` | Per-expense comment thread for real-time chat |

**Key schema decisions:**
- `balances` uses running totals, not on-the-fly aggregation — O(1) reads
- `expense_splits` stores `percentage` and `share_count` alongside resolved `amount` for display
- `edit_logs` uses JSONB `before_json`/`after_json` — queryable, not just displayable
- `user_id_1 < user_id_2` convention — one row per pair per group, no duplicates

### API Design

Full endpoint table in `AI_CONTEXT.md §9`.

- **`/auth/*`** — signup, login, logout, Google OAuth, forgot/reset/change password
- **`/groups/*`** — CRUD, member management, balances, expenses, settlements, activity feed
- **`/expenses/:id`** — detail, edit, delete, comments
- **`/settlements/:id`** — reverse
- **`/invites/:token`** — validate, accept
- **`/users/me`** — profile, cross-group balance summary
- **`WS /socket.io`** — events: `balance:updated`, `comment:new`

### Frontend Structure

```
src/
├── pages/          Login, Signup, Dashboard, GroupDetail,
│                   ExpenseDetail, Profile, Invite,
│                   ForgotPassword, ResetPassword, AuthCallback
├── components/     layout/, groups/, expenses/, settlements/, comments/
├── providers/      SocketProvider.jsx
├── store/          authStore.js (Zustand)
├── hooks/          useGroups, useExpenses, useBalances
└── api/            axiosInstance, auth, groups, expenses, settlements
```

### Deployment

**Backend (Railway):**
- FastAPI service + PostgreSQL plugin in one Railway project
- Start: `alembic upgrade head && uvicorn app.main:socket_app --host 0.0.0.0 --port $PORT`
- Python 3.11 enforced via `runtime.txt`
- `mise.toml` added for attestation bypass
- Live: `https://spliteasy-backend-production.up.railway.app`

**Frontend (Vercel):**
- Build: `npm run build` | Output: `dist`
- `vercel.json` added for React Router SPA routing fix
- Live: `https://spliteasy-frontend.vercel.app`

---

## Part 3 — AI Collaboration Process

### How I Instructed the AI

I started by pasting the verbatim required initial prompt from the assignment brief into Claude (claude.ai — Claude Sonnet 4.6). Key constraints enforced:

1. **"Do not assume requirements"** — Every decision had to come from me answering a specific question.
2. **"Do not recommend technical solutions"** — Claude asked questions and presented tradeoffs; I made the choices.
3. **"Update AI_CONTEXT.md after every answer"** — After each Q&A pair, Claude appended the decision to the relevant section before asking the next question.
4. **"No build plan until enough questions are asked"** — I rejected Claude's first attempt to move to implementation and pushed it to cover all topic areas.

### What Questions the AI Asked

| Topic Area | Question Claude Asked |
|---|---|
| Product goals | "Is this primarily a tracking tool, a payment tool, or both?" |
| Splitwise research | "What did you find most frustrating about Splitwise's UX?" |
| Core workflows | "Walk me through the exact steps from creating a group to a settled balance." |
| User personas | "Who are the 2-3 distinct types of people who would use this?" |
| MVP scope | "If you had to cut 40% of the features, what stays and what goes?" |
| Data model | "Should balances be computed on-the-fly or maintained as running totals?" |
| Authentication | "JWT or server-side sessions? What happens if a user's phone is stolen?" |
| Groups | "When a member is removed, what happens to their historical balance contributions?" |
| Expenses | "For unequal splits, does the UI validate amounts sum to total before submission?" |
| Settlements | "Does 'settle up' mean processing a payment or recording one?" |
| Real-time | "Polling, SSE, or WebSocket?" |
| Deployment | "Where are you deploying? What platforms are you comfortable with?" |
| Testing | "What's the highest-risk part of this codebase?" |
| Tradeoffs | "What are you consciously leaving out or simplifying?" |

### How the Plan Evolved

**1. Auth: JWT → DB Sessions**
After the stolen device question, switched to PostgreSQL server-side sessions with `revoked_at`. Added the `sessions` table and `auth_service.py`.

**2. Balance: On-the-fly → Running Totals**
After the read-performance discussion, switched to the running totals `balances` table. Added `balance_service.py` with upsert logic.

**3. Activity Log: String → JSONB**
After the Disputer Dev persona discussion, switched to JSONB `before_json`/`after_json`. The `edit_log_service.get_activity_feed()` derives display text at query time.

**4. Personas: 3 → 4**
Added Disputer Dev as fourth persona during the edit log discussion.

**5. shadcn → Plain Tailwind**
During implementation, shadcn init kept failing due to jsconfig/tsconfig conflicts with the Vite JS project. Dropped shadcn entirely — all UI built with plain Tailwind utility classes. No functionality lost.

**6. ProfilePage bug → `updateUser({ ...user, ...form })`**
Backend PUT `/users/me` returns `{message: 'Profile updated'}` not a user object. The original code called `updateUser(res.data.data)` which overwrote the user in localStorage with `{message: ...}`, breaking `user.id` everywhere. Fixed by merging form values into existing user object.

### How AI_CONTEXT.md Was Maintained

- Before any code: full Q&A completed, every decision documented
- During build: every schema change, architecture decision, and bug fix added to Section 14
- After deployment: real URLs, real changes, real bugs documented
- File committed to repository on every meaningful change

---

## Part 4 — Tradeoffs

### What I Simplified

- **Debt simplification removed.** A owes B, B owes C is NOT simplified. Raw pairwise balances shown.
- **Multi-currency simplified.** Currency stored per-expense; no live FX conversion on balance display.
- **shadcn removed.** Plain Tailwind used throughout — faster to build, no dependency conflicts.
- **Settlement reversal UI not built.** Endpoint exists; no frontend component in MVP.
- **No pagination UI.** Backend supports pagination; frontend loads first page only.

### What I Hardcoded

- Currency options limited to USD, INR, EUR, GBP in dropdowns
- Session expiry at 30 days
- Invite expiry at 7 days
- Rounding remainder always goes to the payer

### What I Avoided

- Debt simplification graph algorithm — high correctness risk
- httpOnly cookies — requires CSRF handling
- Redis for session lookups — not needed at MVP traffic
- Native mobile app — React Native setup alone would exceed the 2-day budget
- Receipt OCR — requires third-party service integration

### What I Would Improve With More Time

| Improvement | Why |
|---|---|
| Debt simplification | Reduces number of settlements needed in large groups |
| httpOnly cookie session token | Eliminates XSS risk |
| Balance history chart | Show balance trend over time |
| Settlement reversal UI | Endpoint exists; just needs a frontend component |
| Rate limiting on API | Prevents abuse of invite + auth endpoints |
| Email verification at signup | Prevents fake accounts |
| Rotating rounding assignment | Fair distribution of rounding burden |
| UPI deeplink on mobile | One-tap payment flow on mobile |

---

## Deliverables

| Deliverable | Link |
|---|---|
| **Live App** | https://spliteasy-frontend.vercel.app |
| **Backend API + Docs** | https://spliteasy-backend-production.up.railway.app/docs |
| **Frontend GitHub** | https://github.com/shriyashsk/spliteasy-frontend |
| **Backend GitHub** | https://github.com/shriyashsk/spliteasy-backend |
| **AI Tool Used** | Claude (claude.ai) — Claude Sonnet 4.6 |
| **README.md** | In both GitHub repositories |
| **BUILD_PLAN.md** | This file |
| **AI_CONTEXT.md** | Alongside this file |

