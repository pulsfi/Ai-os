# Frontend — Project State

Living record of the AI OS frontend build. Updated at the end of every milestone.

**Stack:** Next.js 16 (App Router, Turbopack) · React 19.2 · TypeScript (strict) ·
Tailwind CSS v4 · shadcn/ui · Framer Motion · TanStack Query · Zustand · Zod ·
React Hook Form · Axios · next-themes.

> Note: `create-next-app` installed **Next 16.2.10**, not 15. Next 16 is a
> superset (Turbopack default, async `params`/`searchParams`, `next lint`
> removed). Built against 16 per the bundled docs in `node_modules/next/dist/docs`.

---

## ✅ Milestone 1 — Architecture & Application Shell (done 2026-07-03)

Scaffold, tooling, theme, and the app shell (sidebar + top nav + routing).
**No feature pages** — all 8 sections are scaffolded placeholders.

### Completed

- Scaffolded `frontend/` (TypeScript strict, Tailwind v4, `src/`, `@/*` alias).
- Installed the full stack + shadcn/ui with 13 base components.
- Dark-futuristic theme: OKLCH design tokens (dark default + light), `glow`
  utility, cyan/violet accent — in `src/app/globals.css`.
- Typed config layer: `env.ts` (Zod-validated), `nav.ts` (data-driven nav),
  `site.ts`.
- Providers composed once in the root layout: theme, TanStack Query, tooltips,
  sonner toaster.
- App shell: collapsible desktop `Sidebar`, mobile `Sheet` drawer, sticky
  `TopNav` (section title + theme toggle), all wired to a Zustand UI store.
- Routing: `(os)` route group with shared `layout`, `loading` (skeleton), and
  `error` (error boundary). `/` → `/dashboard` redirect.
- 8 placeholder pages: dashboard, chat, agents, blockchain, trading, memory,
  terminal, settings — each with page metadata.

### Verified

- `tsc --noEmit` clean · `eslint` clean · `next build` passes (all 8 routes +
  redirect prerendered).
- Dev server: `/` returns 307 → `/dashboard`; shell (nav, brand, placeholder)
  renders; every route returns 200.

### Key files

```
frontend/
├─ src/app/layout.tsx            root: providers + fonts + metadata
├─ src/app/page.tsx              redirect / → /dashboard
├─ src/app/(os)/layout.tsx       shell wrapper
├─ src/app/(os)/{loading,error}.tsx  shared skeleton + error boundary
├─ src/app/(os)/<section>/page.tsx   8 placeholder pages
├─ src/components/layout/        os-shell, sidebar, sidebar-nav, top-nav,
│                                mobile-nav, brand, theme-toggle, page-placeholder
├─ src/components/providers/     app-providers, theme, query
├─ src/components/ui/            13 shadcn components
├─ src/config/                   env.ts, nav.ts, site.ts
├─ src/stores/ui-store.ts        sidebar/drawer state (persisted)
├─ src/types/api.ts              shared API contracts
└─ src/lib/utils.ts              cn()
```

---

## ✅ Milestone 2 — API layer + live Dashboard (done 2026-07-04)

Dashboard connected to the real FastAPI backend. **Zero mock data** — every
widget reads a live endpoint, shows skeletons while loading, and degrades to
an inline error with retry.

### Completed

- **API layer:** `src/lib/api/client.ts` (Axios + error-envelope → typed
  `ApiError`, 30s timeout for cold market sweeps), `schemas.ts` (Zod mirrors
  of the backend contracts — responses are validated, contract drift throws
  `contract_mismatch`), `services.ts` (health/system/solana/market).
- **Hooks:** `src/hooks/use-backend.ts` — TanStack Query hooks with polling
  (health 15s, chain 10s, market 30s) + centralized query keys.
- **Dashboard widgets** (`src/components/dashboard/`): SystemHealthCard
  (/health + /system/info), ChainStatusCard (/solana/status, epoch progress
  bar), WatchlistCard (/market/tokens table w/ divergence warning),
  MarketStatusCard (/market/status providers/cache/scheduler). Shared
  `StatusPill`, `WidgetError`; `FadeIn` motion wrapper (reduced-motion safe).
- **Backend change:** CORS middleware added (`config.settings.cors_origins`,
  GET-only) — without it the browser blocks every request. 33/33 backend
  tests still pass.
- `src/lib/format.ts` — price/money/pct/int/timeAgo formatters.

### Verified

- tsc + eslint clean; `next build` passes.
- Live end-to-end: backend answers with
  `access-control-allow-origin: http://localhost:3010`; /dashboard renders all
  four widgets; /market/tokens returns 4 live tokens (3 providers each).

### Notes

- WebSockets: backend has **no WS endpoints yet** — polling stands in;
  typed TODO recorded in `services.ts` (no fake implementations).

## ✅ Milestone 3 — All feature pages live (done 2026-07-04)

Every section is now a real page against real endpoints. Two NEW backend
capabilities were built to support this (no fakes, per project rule):

### Backend additions (backend/)

- **POST /api/v1/chat** — SSE streaming chat via the Claude API
  (`modules/chat`, model `claude-opus-4-8`). Key-gated like the market
  providers: without `ANTHROPIC_API_KEY` it returns the standard
  `configuration_error` envelope. `GET /chat/status` reports availability.
- **GET /api/v1/agents** (+ `/{name}`, `/{name}/reports`) — read-only
  bridge to the vault's `04 Agents/` markdown (`modules/agents`): status
  from frontmatter, description from the hub note, logs from Reports.md.
  `POST /agents/{name}/{start|stop|restart}` exists as a typed contract but
  **honestly declines** (`accepted: false` + reason) — no process runtime
  until Stage 6.
- CORS now allows POST; chat client closed in lifespan; `.env.example`
  documents `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` / `AGENTS_DIR`.
- Tests: 46/46 pass (13 new: SSE framing, mid-stream errors, key gating,
  synthetic-vault agents fixtures, traversal rejection, honest controls).

### Frontend pages

- **AI Chat** — token-by-token streaming (fetch + ReadableStream SSE parser
  in `src/lib/api/chat-stream.ts`), stop button, honest "not configured"
  banner when the backend has no key.
- **Agent Manager** — 7 status cards from /agents (status, report count,
  last activity), detail sheet with Mission + report log, start/stop/restart
  buttons that surface the backend's decline reason as a toast.
- **Blockchain** — live ChainStatusCard + on-chain rug check
  (/solana/token/{mint}/authorities) with revoked/active verdicts.
- **Trading** — WatchlistCard + Trending (ranked movers) + Token inspector
  (/market/token/{address} + stored history with an honest "requires
  PostgreSQL" state). Read-only by design: no buy/sell until Stage 5.
- **Terminal** — real GET console against the live API (type an endpoint,
  see the actual JSON + latency). Deliberately not a fake shell.
- **Memory** — per-agent knowledge from live /agents; vault memory notes
  clearly marked as awaiting the /vault backend endpoints.
- **Settings** — live config state: /system/info, /chat/status, market
  provider keys (configured/not), cache + scheduler state, API base URL.

### Verified

- Backend: 46/46 pytest; live smoke of /chat/status, /agents (7 real
  agents, pipeline order, Execution=standby), gated control, 404s.
- Frontend: eslint clean, `next build` passes, all 8 routes render 200
  with the new content against the running backend.

## ⏭️ Next — Milestone 4

- Backend /vault endpoints (Memory page's remaining section, notes bridge).
- WebSocket layer for live updates (replaces polling).
- Paper-trading surface on the Trading page once the backend exposes the
  Node paper-trade ledger (or a Python port of it).
- Photon integration: pending the user's API keys — no public API exists,
  so nothing is stubbed.
