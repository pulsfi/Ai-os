"use client";

/**
 * Wallet trading (real money, non-custodial via Phantom).
 *
 * Flow, with the user in control at every step:
 *   connect Phantom → backend BUILDS an unsigned Jupiter swap →
 *   Phantom shows it → user approves → it lands on-chain → Solscan link.
 *
 * The app never holds a key and cannot move funds on its own. Bots never
 * reach this path — it requires a human wallet click by design.
 */
import * as React from "react";
import {
  ArrowDownUp,
  ExternalLink,
  Loader2,
  ShoppingCart,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { executionService } from "@/lib/api/services";
import { ApiError } from "@/lib/api/client";
import { phantom } from "@/lib/phantom";

function shorten(addr: string): string {
  return `${addr.slice(0, 4)}…${addr.slice(-4)}`;
}

export function WalletTradePanel() {
  const [pubkey, setPubkey] = React.useState<string | null>(null);
  const [sol, setSol] = React.useState<number | null>(null);
  const [mint, setMint] = React.useState("");
  const [usd, setUsd] = React.useState("10");
  const [busy, setBusy] = React.useState<null | "buy" | "sell">(null);
  const [lastSig, setLastSig] = React.useState<string | null>(null);

  const refreshBalance = React.useCallback(async (addr: string) => {
    try {
      const bal = await executionService.walletBalance(addr);
      setSol(bal.sol);
    } catch {
      setSol(null);
    }
  }, []);

  async function connect() {
    try {
      const addr = await phantom.connect();
      setPubkey(addr);
      void refreshBalance(addr);
      toast.success(`Connected ${shorten(addr)}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Connect failed");
    }
  }

  async function trade(side: "buy" | "sell") {
    if (!pubkey) return;
    const target = mint.trim();
    if (!target) {
      toast.error("Enter a token mint address");
      return;
    }
    setBusy(side);
    setLastSig(null);
    try {
      const built =
        side === "buy"
          ? await executionService.buildBuy(pubkey, target, Number(usd))
          : await executionService.buildSell(pubkey, target);
      toast.message("Approve the trade in Phantom", { description: built.description });
      const signature = await phantom.signAndSend(built.swap_transaction_b64);
      setLastSig(signature);
      toast.success("Trade submitted on-chain");
      void refreshBalance(pubkey);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Trade failed";
      // A user rejecting in Phantom is not an error worth shouting about.
      if (/reject|declin|cancel/i.test(msg)) toast.info("Trade cancelled in wallet");
      else toast.error(msg);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wallet className="size-4 text-primary" /> Wallet trading
              <Badge variant="outline" className="text-[10px]">real money</Badge>
            </CardTitle>
            <CardDescription>
              Trade with your own Phantom wallet — you approve every trade, the
              app never holds your keys.
            </CardDescription>
          </div>
          {pubkey ? (
            <Badge className="gap-1.5 font-mono">
              <span className="size-2 rounded-full bg-emerald-400" />
              {shorten(pubkey)}
              {sol !== null && <span className="opacity-80">· {sol.toFixed(3)} SOL</span>}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!pubkey ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <p className="max-w-sm text-sm text-muted-foreground">
              Connect Phantom to trade. Your private key stays in the wallet —
              the app only builds trades for you to approve.
            </p>
            {phantom.installed() ? (
              <Button onClick={connect}>
                <Wallet className="size-4" /> Connect Phantom
              </Button>
            ) : (
              <Button asChild variant="outline">
                <a href="https://phantom.app/" target="_blank" rel="noreferrer">
                  Install Phantom <ExternalLink className="size-4" />
                </a>
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
              <p className="flex items-start gap-2 text-xs text-amber-200/90">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                <span>
                  Real funds. Meme coins can go to zero in seconds. Only trade what
                  you can afford to lose, and review every trade in Phantom before
                  approving. This is not financial advice.
                </span>
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Token mint address</label>
              <Input
                value={mint}
                onChange={(e) => setMint(e.target.value)}
                placeholder="e.g. DezXAZ8z7Pnrn… (BONK)"
                className="font-mono text-xs"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground">Buy size (USD)</label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    min={1}
                    value={usd}
                    onChange={(e) => setUsd(e.target.value)}
                    className="font-mono"
                  />
                  <Button
                    className="shrink-0"
                    disabled={busy !== null || !mint.trim() || Number(usd) <= 0}
                    onClick={() => trade("buy")}
                  >
                    {busy === "buy" ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <ShoppingCart className="size-4" />
                    )}
                    Buy
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground">Sell full balance</label>
                <Button
                  variant="secondary"
                  className="w-full"
                  disabled={busy !== null || !mint.trim()}
                  onClick={() => trade("sell")}
                >
                  {busy === "sell" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <ArrowDownUp className="size-4" />
                  )}
                  Sell all → SOL
                </Button>
              </div>
            </div>

            {lastSig && (
              <a
                href={`https://solscan.io/tx/${lastSig}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 text-xs text-primary hover:underline"
              >
                View last trade on Solscan <ExternalLink className="size-3.5" />
              </a>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
