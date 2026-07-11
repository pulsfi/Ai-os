"""Launch confidence scoring — a real multi-factor risk/decision engine.

Instead of buying every new token, the sniper scores each candidate 0-100
from MEASURABLE on-chain + flow signals and only enters when the score
clears a threshold with no hard-reject. Every factor carries its own
points and a human reason, so each decision is fully explainable and
logged in the trade note.

Honesty rules baked in:
  * Nothing is fabricated. A signal we cannot measure counts as UNKNOWN
    (zero points) — never invented.
  * Missing DEMAND data (no flow) can't reach the threshold, so the bot
    stays out rather than guessing (the spec's "reject if info missing").
  * Active mint/freeze authority = an immediate HARD REJECT (real rug /
    honeypot signals), regardless of an otherwise good score.

Signals used come from data the system already has:
  RPC (mint/freeze authority) · Helius (buys/sells, unique wallets,
  swaps) · pump.fun (market cap, age).
"""

from dataclasses import dataclass, field


@dataclass
class Factor:
    """One scored signal: what it contributed and why."""

    name: str
    points: float
    max_points: float
    detail: str


@dataclass
class ConfidenceScore:
    """The decision-engine verdict for one launch."""

    score: float  # 0-100
    approved: bool
    factors: list[Factor] = field(default_factory=list)
    rejects: list[str] = field(default_factory=list)  # hard-reject reasons

    def note(self) -> str:
        """Compact one-line summary for the trade log."""
        top = ", ".join(f"{f.name} {f.points:.0f}/{f.max_points:.0f}" for f in self.factors)
        return f"confidence {self.score:.0f}/100 [{top}]"


def _scaled(value: float | None, lo: float, hi: float, max_pts: float) -> float:
    """Linear points between lo (0 pts) and hi (max_pts); None -> 0."""
    if value is None:
        return 0.0
    if value <= lo:
        return 0.0
    if value >= hi:
        return max_pts
    return round((value - lo) / (hi - lo) * max_pts, 1)


def score_launch(
    *,
    mcap_usd: float | None,
    age_s: float | None,
    mint_revoked: bool | None,   # True=revoked(safe), False=active(rug), None=unknown
    freeze_revoked: bool | None,
    buy_ratio_pct: float | None,
    unique_wallets: int | None,
    swaps: int | None,
    min_mcap_usd: float,
    max_mcap_usd: float,
    max_age_s: float,
    min_confidence: float = 55.0,
    min_wallets: int = 3,
) -> ConfidenceScore:
    """Score one launch. Authorities are GATES (hard-reject if active) worth
    only a little score; the BUY decision is driven by real demand. Weights
    (max 100): mint 8, freeze 8, buy-ratio 40, wallets 28, swaps 8,
    mcap-band 4, age 4."""
    factors: list[Factor] = []
    rejects: list[str] = []

    # --- authority safety (hard gates) -----------------------------------
    if mint_revoked is False:
        rejects.append("mint authority ACTIVE — creator can inflate supply")
        factors.append(Factor("mint", 0, 8, "active (rug risk)"))
    elif mint_revoked is True:
        factors.append(Factor("mint", 8, 8, "revoked"))
    else:
        factors.append(Factor("mint", 0, 8, "unknown"))

    if freeze_revoked is False:
        rejects.append("freeze authority ACTIVE — wallets can be frozen (honeypot)")
        factors.append(Factor("freeze", 0, 8, "active (honeypot risk)"))
    elif freeze_revoked is True:
        factors.append(Factor("freeze", 8, 8, "revoked"))
    else:
        factors.append(Factor("freeze", 0, 8, "unknown"))

    # --- demand quality (flow) — drives the decision ---------------------
    br = _scaled(buy_ratio_pct, 50.0, 85.0, 40.0)
    factors.append(
        Factor("buy_ratio", br, 40, f"{buy_ratio_pct}% buys" if buy_ratio_pct is not None else "unknown")
    )
    uw = _scaled(unique_wallets, 3, 20, 28.0)
    factors.append(
        Factor("wallets", uw, 28, f"{unique_wallets} wallets" if unique_wallets is not None else "unknown")
    )
    # A single/handful of wallets buying = likely wash trading or one whale,
    # not broad demand — hard reject even if the buy ratio looks great.
    if unique_wallets is not None and unique_wallets < min_wallets:
        rejects.append(f"only {unique_wallets} wallet(s) — no broad demand (wash risk)")
    sw = _scaled(swaps, 4, 30, 8.0)
    factors.append(Factor("swaps", sw, 8, f"{swaps} swaps" if swaps is not None else "unknown"))

    # --- market context --------------------------------------------------
    in_band = mcap_usd is not None and min_mcap_usd <= mcap_usd <= max_mcap_usd
    factors.append(
        Factor("mcap", 3 if in_band else 0, 3, f"${mcap_usd:,.0f}" if mcap_usd else "unknown")
    )
    fresh = age_s is not None and age_s <= max_age_s
    age_pts = _scaled(max_age_s - age_s, 0, max_age_s, 3.0) if fresh else 0.0
    factors.append(
        Factor("age", age_pts, 3, f"{int(age_s)}s old" if age_s is not None else "unknown")
    )

    score = round(sum(f.points for f in factors), 1)
    approved = not rejects and score >= min_confidence
    if not approved and not rejects and score < min_confidence:
        rejects.append(f"score {score:.0f} below the {min_confidence:.0f} threshold")
    return ConfidenceScore(score=score, approved=approved, factors=factors, rejects=rejects)


def score_pumpfun_launch(
    *,
    mcap_usd: float | None,
    mcap_growth_pct_per_min: float | None,  # buy-pressure proxy; None=unconfirmed
    bonding_progress_pct: float | None,
    reply_count: int | None,
    age_s: float | None,
    mint_revoked: bool | None,
    freeze_revoked: bool | None,
    min_mcap_usd: float,
    max_mcap_usd: float,
    max_age_s: float,
    min_confidence: float = 55.0,
    require_growth_confirmation: bool = True,
) -> ConfidenceScore:
    """Confidence for a token still on the pump.fun bonding curve.

    Helius/DEX aggregators are BLIND to bonding-curve trades (they only see
    a token once it graduates to Raydium), so the generic `score_launch`
    can never clear its threshold for a fresh launch. This variant scores
    the signals pump.fun DOES expose:

      * market cap (real, off the creator-only floor),
      * market-cap VELOCITY — the buy-pressure proxy: a launch climbing is
        one people are actively buying (this replaces buy/sell flow),
      * bonding-curve progress — how much demand has committed,
      * community replies, token age, and RPC authority state.

    "Confirmation" entry: velocity needs a second observation to exist, so
    a launch is never bought on its first sighting — only once we've SEEN
    it climb. `require_growth_confirmation=False` relaxes that gate for the
    stateless research card (a single snapshot has no velocity).

    Hard rejects: active mint/freeze authority (rug/honeypot), market cap
    outside the band (no price yet, or already run up), and — when
    confirming — a launch that is flat or dumping.

    Weights (max 100): mint 8, freeze 8, velocity 34, mcap-band 16,
    bonding 16, replies 10, age 8.
    """
    factors: list[Factor] = []
    rejects: list[str] = []

    # --- authority safety (hard gates) -----------------------------------
    if mint_revoked is False:
        rejects.append("mint authority ACTIVE — creator can inflate supply")
        factors.append(Factor("mint", 0, 8, "active (rug risk)"))
    elif mint_revoked is True:
        factors.append(Factor("mint", 8, 8, "revoked"))
    else:
        factors.append(Factor("mint", 0, 8, "unknown"))

    if freeze_revoked is False:
        rejects.append("freeze authority ACTIVE — wallets can be frozen (honeypot)")
        factors.append(Factor("freeze", 0, 8, "active (honeypot risk)"))
    elif freeze_revoked is True:
        factors.append(Factor("freeze", 8, 8, "revoked"))
    else:
        factors.append(Factor("freeze", 0, 8, "unknown"))

    # --- buy pressure: market-cap velocity (drives the decision) ---------
    if mcap_growth_pct_per_min is None:
        factors.append(Factor("velocity", 0, 34, "awaiting confirmation"))
        if require_growth_confirmation:
            rejects.append("no second reading yet — waiting to confirm it's climbing")
    else:
        vel = _scaled(mcap_growth_pct_per_min, 1.0, 25.0, 34.0)
        factors.append(Factor("velocity", vel, 34, f"{mcap_growth_pct_per_min:+.0f}%/min mcap"))
        if require_growth_confirmation and mcap_growth_pct_per_min <= 0:
            rejects.append(
                f"mcap flat/falling ({mcap_growth_pct_per_min:+.0f}%/min) — no buy pressure"
            )

    # --- market context (hard band) --------------------------------------
    in_band = mcap_usd is not None and min_mcap_usd <= mcap_usd <= max_mcap_usd
    factors.append(
        Factor("mcap", 16 if in_band else 0, 16, f"${mcap_usd:,.0f}" if mcap_usd else "unknown")
    )
    if mcap_usd is None or mcap_usd < min_mcap_usd:
        rejects.append("market cap below the floor — no real buyers yet")
    elif mcap_usd > max_mcap_usd:
        rejects.append(f"market cap ${mcap_usd:,.0f} above the band — too late / priced in")

    # --- committed demand: bonding-curve progress ------------------------
    bp = _scaled(bonding_progress_pct, 0.0, 20.0, 16.0)
    factors.append(
        Factor("bonding", bp, 16,
               f"{bonding_progress_pct:.0f}% to graduation" if bonding_progress_pct is not None else "unknown")
    )

    # --- community + freshness -------------------------------------------
    rp = _scaled(reply_count, 0, 25, 10.0)
    factors.append(
        Factor("replies", rp, 10, f"{reply_count} replies" if reply_count is not None else "unknown")
    )
    fresh = age_s is not None and age_s <= max_age_s
    age_pts = _scaled(max_age_s - age_s, 0, max_age_s, 8.0) if fresh else 0.0
    factors.append(
        Factor("age", age_pts, 8, f"{int(age_s)}s old" if age_s is not None else "unknown")
    )

    score = round(sum(f.points for f in factors), 1)
    approved = not rejects and score >= min_confidence
    if not approved and not rejects and score < min_confidence:
        rejects.append(f"score {score:.0f} below the {min_confidence:.0f} threshold")
    return ConfidenceScore(score=score, approved=approved, factors=factors, rejects=rejects)
