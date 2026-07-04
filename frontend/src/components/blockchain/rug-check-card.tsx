"use client";

/**
 * On-chain rug check — queries /solana/token/{mint}/authorities live.
 * Revoked mint+freeze authorities = supply and transfers are immutable.
 */
import * as React from "react";
import { Search, ShieldAlert, ShieldCheck } from "lucide-react";

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
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { useTokenAuthorities } from "@/hooks/use-backend";

function AuthorityRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border p-3">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="break-all font-mono text-xs text-muted-foreground">
          {value ?? "revoked"}
        </p>
      </div>
      <Badge variant={value === null ? "default" : "destructive"}>
        {value === null ? "revoked · safe" : "ACTIVE · risk"}
      </Badge>
    </div>
  );
}

export function RugCheckCard() {
  const [input, setInput] = React.useState("");
  const [mint, setMint] = React.useState("");
  const query = useTokenAuthorities(mint);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Token rug check</CardTitle>
        <CardDescription>
          Mint &amp; freeze authority state, read directly from mainnet
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setMint(input.trim());
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="SPL token mint address…"
            className="font-mono text-xs"
          />
          <Button type="submit" size="icon" disabled={!input.trim()}>
            <Search className="size-4" />
          </Button>
        </form>

        {query.isFetching && (
          <div className="space-y-2">
            <Skeleton className="h-16 rounded-lg" />
            <Skeleton className="h-16 rounded-lg" />
          </div>
        )}

        {query.isError && !query.isFetching && (
          <WidgetError error={query.error} onRetry={() => void query.refetch()} />
        )}

        {query.data && !query.isFetching && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/50 p-3 text-sm">
              {query.data.is_fully_revoked ? (
                <>
                  <ShieldCheck className="size-5 text-primary" />
                  <span>
                    Both authorities revoked — supply is fixed, accounts cannot be frozen.
                  </span>
                </>
              ) : (
                <>
                  <ShieldAlert className="size-5 text-destructive" />
                  <span>
                    An authority is still active — the owner can{" "}
                    {query.data.mint_authority ? "mint new supply" : ""}
                    {query.data.mint_authority && query.data.freeze_authority ? " and " : ""}
                    {query.data.freeze_authority ? "freeze holder accounts" : ""}.
                  </span>
                </>
              )}
            </div>
            <AuthorityRow label="Mint authority" value={query.data.mint_authority} />
            <AuthorityRow label="Freeze authority" value={query.data.freeze_authority} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
