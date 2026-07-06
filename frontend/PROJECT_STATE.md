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

## ✅ Milestone 4 — Pump.fun discovery + paper-trading ledger (done 2026-07-04)

### Backend additions

- **`modules/market/pumpfun.py`** — read-only pump.fun discovery client
  against `frontend-api-v3.pump.fun` (unofficial but public; verified live).
  Normalized `PumpCoin` model with bonding-curve progress toward graduation.
  Endpoints: `GET /market/pumpfun/new`, `/pumpfun/graduating`,
  `/pumpfun/coin/{mint}`. Rate-guarded (delay, not drop) like the other
  providers; failures are honest `external_service_error`s.
- **`modules/trading/paper_service.py`** — read-only bridge to the Node
  scalper's SQLite ledger (`09 Automation/market/market.db`), opened with
  `mode=ro` so this process physically cannot write. Endpoints:
  `GET /trading/summary` (PnL, win rate, open/closed counts) and
  `GET /trading/trades` (log, `?status=open|closed`). Missing DB →
  `available: false`, never fake zeros-as-data.
- No buy/sell endpoints anywhere — Stage 5 gate intact.
- Tests: 55/55 (9 new: pumpfun parsing/progress/errors via MockTransport,
  synthetic SQLite ledger, read-only enforcement, honest missing-DB state).

### Frontend

- **Trading page** now leads with the **Paper trading ledger** (realized
  PnL, win rate, trade log with entry/exit/reasoning — the scalper's real
  track record) and **Pump.fun launches** (New / Graduating toggle,
  bonding-curve progress bars, live badges), above Trending, Watchlist,
  and the Token inspector.

### Verified live

- `/market/pumpfun/new` returned coins launched seconds earlier;
  `/trading/summary` returned the real ledger (5 trades, +$2.09 realized,
  50% win rate, 14 snapshots); Trading page renders all cards.
- tsc + eslint clean; `next build` passes.

## ✅ Milestone 5 — Multi-bot paper-trading runtime (done 2026-07-04)

The "multi bot, all the time" milestone: three strategy bots run as real
asyncio loops inside the backend, trading virtual USD against live data,
with REAL start/stop/restart from the UI. PAPER MODE ONLY — no wallets,
no keys, no signing anywhere in the module tree (Stage 5 gate intact).

### Backend (`modules/bots/`)

- **`ledger.py`** — dedicated SQLite ledger (`backend/data/paper_bots.db`,
  WAL), single writer = this process. Open/close trades, per-bot stats.
- **`strategies.py`** — three styles sharing one interface:
  `sniper` (new pump.fun launches with early traction), `graduate`
  (bonding-curve graduation momentum ≥85%), `trend` (watchlist 24h movers
  on real merged prices — the baseline bot). Pump prices derived
  mcap/1B supply, stated in every entry note.
- **`runner.py`** — per-bot loop: mark-to-market → take-profit/stop-loss/
  max-hold exits → new entries. Every tick error-contained; a failing
  provider costs one tick, never the loop.
- **`manager.py`** — fleet registry, real start/stop/restart, honest
  `BotControlResult`. Lifespan autostart via `BOTS_AUTOSTART=true`
  (set in backend/.env), clean shutdown on exit.
- Endpoints: `GET /bots`, `GET /bots/trades`, `GET /bots/{id}/trades`,
  `POST /bots/{id}/{start|stop|restart}` (REAL, unlike /agents).
- Tests: 65/65 (10 new: ledger math/isolation, sniper filters, runner
  TP/SL/lifecycle/error-survival, endpoint contracts).

### Frontend

- **BotFleetCard** leads the Trading page: per-bot cards (state with
  pulse, open/closed, realized PnL, win rate, ticks/errors), real
  Start/Stop/Restart buttons, and a Trades drawer showing the live
  ledger with entry/exit notes.

### Verified live

- Boot → all three bots `running`; within one tick the fleet held BONK
  (trending +4.82%, 3 providers) and three graduating pump.fun coins.
- `POST /bots/sniper/stop` → `accepted:true, state:stopped`; start →
  running again. tsc + eslint clean; `next build` passes; Trading page
  renders the fleet.

## ✅ Milestone 6 — Performance review + WebSocket live layer (done 2026-07-05)

### Backend

- **`GET /bots/performance`** — track record per bot + whole fleet:
  equity curve of cumulative REALIZED PnL (closed trades only — unrealized
  gains never flatter the chart), win rate, avg/best/worst trade.
- **`ws://…/api/v1/ws`** — WebSocket pushing a full fleet snapshot
  (bots + latest 20 trades) every 3s. Read-only: inbound messages are
  ignored, controls stay on REST. `websockets` added to requirements.
- Tests: 68/68 (3 new: chronological curve input, performance contract,
  WS handshake + frame shape via TestClient).

### Frontend

- **`src/lib/ws.ts`** — typed WS client: Zod-validates every frame
  (malformed frames dropped, never rendered), reconnects with capped
  exponential backoff.
- **`useFleetLive`** — WS-first fleet state with the 10s REST poll as
  automatic fallback; the fleet card badge shows "live socket" vs
  "polling" honestly.
- **PerformanceCard** on the Trading page: dependency-free SVG equity
  curve (zero-line, win/loss coloring), per-bot selector chips, and a
  strategy comparison table (closed, W/L, win rate, PnL, avg/best/worst).

### Verified live

- `/bots/performance` returned the fleet's real overnight record:
  4 closed trades, graduate 0/3 (-$2.43), trend 1/1 (+$0.32).
- WS: two consecutive frames 3s apart with full fleet + 7 trades.
- tsc + eslint clean; `next build` passes; Trading page renders the
  performance card.

## ✅ Milestone 7 — Helius, strategy tuning, vault bridge (done 2026-07-05)

### Helius plugged in

- User's Helius API key added to `backend/.env` and `09 Automation/.env`
  (both gitignored — the key is NOT in the repo). The existing `rpc_url`
  property upgrade kicked in: RPC client now runs 2 endpoints (Helius
  primary + public fallback). Verified live: /solana/status served by
  `mainnet.helius-rpc.com`.

### Data-driven strategy fix

- Graduation Rider's first track record (0/3, -$2.43) showed entries at
  99.9–100% bonding progress buy the top. Entry is now a BAND: 85–98.5%.
  Regression test locks the lesson in (`TooLate`/`AtTop` coins rejected).

### Vault bridge (backend `modules/vault/`)

- Read-only notes API over an ALLOWLIST of folders (10 Memory, 12 Daily
  Notes, 00 Dashboard): `GET /vault/dirs`, `/vault/notes?dir=`,
  `/vault/note?path=`. Containment enforced in one place — traversal,
  absolute paths, non-.md, and non-allowlisted folders all 404
  (parametrized security tests; the vault holds .env files, so this is
  the highest-stakes surface). Tests: 79/79.

### Frontend

- **Memory page** now browses real vault notes: folder tabs from
  /vault/dirs, note list (newest first), full markdown viewer — Training
  Log and Memory Hub render live. Honest-empty-state card removed
  because the real thing exists now.

## ✅ Milestone 8 — Helius flow data + daily-report writer (done 2026-07-05)

### Backend

- **`modules/market/helius.py`** — Helius Enhanced Transactions client
  (key-gated): `GET /market/activity/{mint}` summarizes the latest
  parsed transactions into buys vs sells (from swap token legs), buy
  ratio, unique wallets, tx/min. Rate-guarded; no key = honest
  `configuration_error`. Note: native-SOL legs aren't classifiable
  (SOL shows swaps but 0/0 buys/sells); SPL tokens classify fully.
- **First vault WRITE path** — `POST /vault/daily-report` appends the
  fleet's performance table to TODAY's `12 Daily Notes/` note (created
  with the vault's frontmatter conventions if absent). The target path
  is computed server-side from the date — client input never reaches
  the filesystem. Append-only (tested: never overwrites).
- Tests: 86/86 (7 new: swap classification, empty history, key gate,
  upstream errors, report markdown, note creation, append-not-destroy).

### Frontend

- **Token inspector** gains a "Live flow" section: buy/sell pressure
  bar, unique wallets, tx rate, last-trade age (30s refresh).
- **Memory page** gains "Write daily report" — writes via the backend,
  toasts the path, jumps to the 12 Daily Notes folder.

### Verified live

- BONK: 50 txs sampled → 62.5% buy pressure (5 buys/3 sells), 24
  wallets, 11 tx/min, served through the user's Helius key.
- Daily report written to `12 Daily Notes/2026-07-05.md` with real
  fleet stats — and the tuned Graduation Rider now shows a 50% win
  rate (was 0% before the 85–98.5% entry band).

## ✅ Milestone 9 — Pro trading behaviors (done 2026-07-05)

Three behaviors real scalpers use, all paper-mode:

- **Trailing stops** (runner): once a position's peak gain clears
  `trail_after_pct`, it closes when price gives back `trail_drop_pct`
  from the peak — locks profit instead of round-tripping to the fixed
  stop. Per-bot: sniper 15/10, graduate 8/5, trend 1.5/1.
- **Flow-gated sniper**: the Launch Sniper now requires Helius flow
  confirmation before entering a fresh launch — ≥3 swaps, ≥3 distinct
  wallets, ≥55% buy ratio. Failed/unavailable flow lookups skip the
  coin (conservative). Without a key the gate is off and the entry
  note says so honestly.
- **Auto daily report**: `DailyReportScheduler` writes the fleet report
  into `12 Daily Notes/` every day at 20:00 UTC (config:
  `DAILY_REPORT_ENABLED/HOUR_UTC`, on in the local .env) — same
  constrained append-only write path as the manual button.

Tests: 95/95 (9 new: trail lock-in + not-armed, flow accept/reject/
fail-closed/gate-off, scheduler timing math, write_now). Verified live:
all bots running with trail configs, scheduler started at 20:00 UTC.

## ✅ Milestone 12 — Stage 5 SAFE FOUNDATION (done 2026-07-05)

Live-execution groundwork, built the responsible way. SHIPS DISARMED.
No wallet, no private key, no transaction signing anywhere in the tree.

### Backend (`modules/execution/`)

- **RiskEngine** — the gate every order passes: per-order size cap,
  daily-loss auto-halt (resets at UTC midnight), max concurrent
  positions, and a global kill switch that can only HALT. Denials are
  the default; disarmed = everything blocked.
- **DryRunExecutor** — fetches a REAL Jupiter quote for the intended
  swap (exercises the whole route), then records a SIMULATED fill.
  Builds/signs/sends nothing. Survives quote failure honestly.
- **LiveExecutor** — deliberate stub; raises `LiveExecutionUnavailable`
  with the exact steps building it responsibly requires. Even
  `EXECUTION_MODE=live` returns the dry-run executor (safety over config).
- **Readiness scorecard** — go-live gates: ≥50 closed trades, ≥55% win
  rate, ≥$25 realized PnL, ≥7 days of record. All must pass.
- API: `GET /execution/status`, `/execution/readiness`,
  `POST /execution/kill/{on|off}`, `POST /execution/dry-run`. No arm
  endpoint — arming is env-only (`EXECUTION_ARMED`, default false).
- Tests: 118/118 (16 new: disarmed-by-default, caps, loss-halt, kill
  switch, dry-run w/ real+failed quote, live unavailable, readiness).

### Frontend

- **ExecutionPanel** on the Trading page: armed/disarmed/halted state,
  hard risk limits, the go-live scorecard (per-gate pass/fail), and a
  kill switch. No "go live" button — that's an operator env decision.

### Verified live

- Status: `armed=false, live_available=false, mode=dry_run`.
- Readiness: 3/4 gates green, held by the 7-day track-length gate —
  the system correctly refuses to call itself ready.
- Kill switch on/off round-trip confirmed.

> NOTE on the paper numbers: current paper win rate / PnL read very high
> because pump.fun positions are priced by the mcap/1B proxy, which
> exaggerates % moves on volatile launches. That inflation is exactly
> why the readiness gate also requires days of record and why real
> dry-run Jupiter quotes now feed the eventual live path — paper PnL is
> not trusted at face value.

## ✅ Milestone 13 — Real-money trading via Phantom (non-custodial) (done 2026-07-05)

Real trading, the safe way: the backend BUILDS trades, the user's own
wallet SIGNS them. No private key ever touches the server or the repo.

### Backend (`modules/execution/manual_swap.py`)

- **ManualSwapBuilder** — builds a real Jupiter swap for the user's
  PUBLIC key and returns it UNSIGNED (base64). Buy = SOL→token sized in
  USD (converted via the live SOL price); sell = token→SOL for the full
  wallet balance (read via RPC `getTokenAccountsByOwner`). Guard rails
  still apply: the global kill switch halts building, and a per-trade
  USD cap (`MANUAL_TRADE_MAX_USD`, default $100) blocks fat-finger buys.
- Read-only `getBalance` / token-balance helpers added to the RPC client.
- Endpoints: `GET /execution/wallet/{pubkey}/balance`,
  `POST /execution/trade/build-buy`, `.../build-sell`. None of them can
  move funds — they only return an unsigned transaction.
- Jupiter host updated to the current `lite-api.jup.ag/swap/v1` (the old
  `quote-api.jup.ag/v6` was retired / no longer resolves).
- Tests: 125/125 (7 new: unsigned-tx build, kill-switch halt, buy cap,
  no-route error, full-balance sell, empty-holdings refusal).

### Frontend

- **WalletTradePanel** on the Trading page: Connect Phantom (or install
  prompt), live SOL balance, mint input, buy-by-USD + sell-all buttons.
  Flow: backend builds → Phantom shows the trade → user approves →
  on-chain → Solscan link. A prominent real-funds risk warning; wallet
  rejections are handled quietly. Uses `@solana/web3.js` only to hand
  Phantom the transaction (`src/lib/phantom.ts`).

### The safety line (unchanged)

- **Bots stay paper.** They have no key and cannot reach the wallet path
  — autonomous live trading is still gated behind the go-live scorecard.
  Only the human, clicking Phantom, can execute real trades.

### Verified live

- Balance read: real 9.17M SOL returned for a known mainnet address.
- Build-buy: a real 848-byte unsigned Jupiter tx for ~$5 of BONK,
  ready for Phantom to sign. tsc/eslint/next build clean.

## ✅ Milestone 14 — Stage 6: the 7-agent pipeline runs live (done 2026-07-05)

The vault's 7 agents are no longer static notes — they run as a live
control loop over the REAL modules, every 60s. No invented cognition:
each agent queries live data / live system state and emits a real result.

### Backend (`modules/agents/runtime.py`)

- **AgentRuntime** threads a shared context through the pipeline
  (Research → Strategy → Risk → Execution → Monitoring → Learning →
  Documentation) each cycle. Real jobs:
  - Research: live pump.fun new launches
  - Strategy: live bot-fleet state + exposure
  - Risk: risk-engine posture (limits, daily PnL, kill switch)
  - Execution: execution state (reports only — gate unchanged)
  - Monitoring: data-provider health
  - Learning: paper track record → best/worst strategy, current lesson
  - Documentation: cycle summary (the scheduler still writes the note)
- Error-contained: one failing agent never stops the pipeline.
- The vault markdown stays the source of truth for mission/rules/reports;
  the runtime overlays live state onto each agent.
- Control endpoints are now REAL: `POST /agents/{name}/{start|stop|restart}`
  toggles the agent in the running pipeline. New: `GET /agents/runtime`
  (cadence, cycles, per-agent state, activity feed),
  `GET /agents/{name}/activity`. Autostarts via lifespan
  (`AGENTS_RUNTIME_ENABLED`, `AGENTS_CYCLE_SECONDS`).
- Tests: 131/131 (8 new: full-cycle ticks, disable-skips-others,
  error containment, real control state changes, activity feed).

### Frontend (Agent Manager)

- Live pipeline banner (running badge, cycle count, cadence, active
  count). Each card shows a live runtime badge (live/idle/stopped/error),
  the agent's current one-line output, run count, and last-run age.
  Controls really start/stop/restart agents. The detail drawer gains a
  **Live activity** feed above Mission + Reports.

### Verified live

- Pipeline running: all 7 agents produced real ticks in cycle 1 —
  Research saw 8 launches (newest ALPHA), Strategy 3/3 bots + 2 open,
  Monitoring 4 providers healthy, Learning the fleet record.
- Stop/start of an agent confirmed to change runtime state.
- tsc/eslint/next build clean.

> The full backend roadmap (Stages 1–6) is now implemented. Stage 5 live
> execution stays deliberately gated: bots are paper-only (no key), and
> real trades require a human Phantom approval.

## 🚧 Stage 7 — Live-trading hardening (in progress, 2026-07-06)

### Done this pass

- **Paper/Live switch** (`POST /execution/mode/{paper|live}`) — a
  segmented toggle in the execution panel. Paper always allowed; **Live
  is refused (409) unless the readiness scorecard is fully green** — the
  gate is now enforced in code. Surfaced the live-trading controls to the
  top of the Trading page + a PAPER/LIVE pill in the ticker.
- **#1 Honest paper pricing** — every simulated exit takes a slippage
  haircut (`BOTS_EXIT_SLIPPAGE_BPS`, 2%) and per-trade gains are capped
  (`BOTS_MAX_GAIN_PCT`, +100%), killing the mcap/1B moonshot artifacts.
- **#2 Return-plausibility gate** — the scorecard fails when the avg
  paper trade exceeds `GOLIVE_MAX_AVG_TRADE_PCT` (30%), so inflated
  returns can never green-light live.
- **#4 Wallet exposure guard** — `MANUAL_DAILY_BUY_LIMIT_USD` ($500)
  caps total real USD bought per UTC day, on top of the per-trade cap.
- **Reset record** — `POST /bots/reset` + a confirm-guarded button on the
  Performance card, so the track record can start clean under the new
  pricing (wiped the 197 old inflated trades; scorecard is honest now).
- Tests: 139/139. Verified live: live blocked at the plausibility +
  track-length gates; reset produced a clean 0-trade scorecard.

### Done (2026-07-06, second pass)

- **#5 Fill reconciliation** — `modules/execution/live_ledger.py`: real
  Phantom-signed trades are recorded (`POST /execution/trade/record`) and
  reconciled against the chain via RPC `getSignatureStatuses`
  (submitted → confirmed/failed). `GET /execution/trades` reconciles any
  pending. The wallet panel records every trade automatically and shows a
  live-trade history with status + Solscan links. Read-only chain access.
- **#7 Alerts** — `modules/alerts`: an in-app ring buffer (works with
  zero config) that also pushes to Telegram when `TELEGRAM_BOT_TOKEN` +
  `TELEGRAM_CHAT_ID` are set. Emits on kill switch, PAPER⇄LIVE switch,
  and every real trade. `GET /alerts`, `POST /alerts/test`. Dashboard
  AlertsCard shows the feed, toasts new alerts, has a Test button.
- Tests: 150/150 (11 new: live-ledger confirm/fail/pending/reconcile/
  idempotent/error-safe, alert buffer + endpoints + kill-switch alert).

### Done (2026-07-06, third pass)

- **#6 infrastructure — editable bot configs from the UI.** Each bot has
  a Tune sheet (sliders icon) to adjust position size, max positions,
  take-profit, stop-loss, and trailing stops. `PATCH /bots/{id}/config`
  applies changes to the live runner and persists them
  (`data/bot_overrides.json`, gitignored) so they survive restarts.
  Paper-only; validated server-side. Tests cover the persist/reload cycle.
  (Actual data-driven *retuning* still waits for the freshly-reset record
  to build a few clean days.)

### Fix (2026-07-06) — per-bot pricing + strategy selectivity

The single 2% exit haircut was too blunt: it destroyed the Trend
Scalper's 3%-margin trades (turning wins into losses) while barely
mattering to the Sniper. Also the Sniper was genuinely negative
(15% win rate, capped winners can't beat 85% losers).

- **Slippage/cap are now per-bot** (`BotConfig.exit_slippage_bps` +
  `max_gain_pct`, tunable in the UI): trend 0.25% (liquid watchlist),
  graduate 1%, sniper 1.5% + 300% cap (fat-tail wins). The runner reads
  config; explicit constructor args still override (tests).
- **Sniper is far more selective** — entry now needs ≥8 swaps, ≥6
  wallets, ≥65% buy ratio, mcap $8k–45k (was 3/3/55%). Fewer, higher-
  conviction trades to lift the win rate. Stop tightened 25%→18%.
- Wiped the 97 broken-pricing trades for a clean record.
- Tests: 153/153.

### Remaining Stage 7

- **#3 Bot signing path** — DELIBERATELY gated: needs a backend key + a
  PROVEN record. The paper record is still forming; nothing proves an
  edge yet. Not built.
- **#6 retune** — continue from the honest record as clean days accrue.
