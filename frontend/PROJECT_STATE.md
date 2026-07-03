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

## ⏭️ Next — Milestone 2: API layer & data hooks

- Axios instance (`src/lib/api/client.ts`) with `apiBaseUrl`, error-envelope
  interceptor, typed request helpers.
- Per-domain services: `health`, `solana`, `market` (mirror the FastAPI
  endpoints already live: `/health`, `/solana/*`, `/market/*`).
- TanStack Query hooks per service; Zod response schemas in `src/types`.
- Missing endpoints get a typed service stub with `TODO` — **no mock data**.

## Backlog (later milestones)

- Feature pages (dashboard metrics, agents, blockchain, trading, memory,
  terminal, settings) wired to the API layer.
- WebSocket layer for live updates (agent status, logs, metrics, trades).
- AI chat page. Framer Motion transitions. Global toasts on mutations.
