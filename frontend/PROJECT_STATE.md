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

## ⏭️ Next — Milestone 3: Blockchain + Trading pages

- Blockchain page: /solana/status detail + token authority rug-check lookup.
- Trading page: /market/tokens + /market/trending + /market/history charts.
- Then: Agents, Memory (vault bridge endpoints TBD on backend), Terminal,
  Settings, AI Chat; WebSocket layer when the backend exposes it.
