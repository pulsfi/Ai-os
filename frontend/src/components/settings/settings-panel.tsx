"use client";

/**
 * Settings — real configuration state read from the backend:
 * app identity (/system/info), assistant (/chat/status), market providers
 * (/market/status), plus the frontend's own connection config.
 *
 * Secrets are configured in backend/.env, never through the browser —
 * this page shows WHAT is configured, not the values.
 */
import { Bot, Database, Globe, KeyRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { WidgetError } from "@/components/dashboard/widget-error";
import { apiBaseUrl } from "@/config/env";
import { useChatStatus, useMarketStatus, useSystemInfo } from "@/hooks/use-backend";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

export function SettingsPanel() {
  const system = useSystemInfo();
  const chat = useChatStatus();
  const market = useMarketStatus();

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Globe className="size-4 text-primary" /> Connection
          </CardTitle>
          <CardDescription>How this UI reaches the backend</CardDescription>
        </CardHeader>
        <CardContent className="divide-y">
          <Row label="API base URL" value={<code className="font-mono text-xs">{apiBaseUrl}</code>} />
          <Row
            label="Backend"
            value={
              system.isLoading ? (
                <Skeleton className="h-4 w-24" />
              ) : system.isError ? (
                <Badge variant="destructive">unreachable</Badge>
              ) : (
                <Badge>connected</Badge>
              )
            }
          />
          {system.data && (
            <>
              <Row label="Application" value={<code className="font-mono text-xs">{system.data.app_name} v{system.data.version}</code>} />
              <Row label="Environment" value={system.data.environment} />
              <Row label="Debug" value={system.data.debug ? "on" : "off"} />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Bot className="size-4 text-primary" /> AI assistant
          </CardTitle>
          <CardDescription>Claude API configuration (key lives in backend/.env)</CardDescription>
        </CardHeader>
        <CardContent className="divide-y">
          {chat.isLoading && <Skeleton className="h-16 rounded" />}
          {chat.isError && <WidgetError error={chat.error} onRetry={() => void chat.refetch()} />}
          {chat.data && (
            <>
              <Row
                label="Status"
                value={
                  chat.data.configured ? (
                    <Badge>configured</Badge>
                  ) : (
                    <Badge variant="secondary">not configured</Badge>
                  )
                }
              />
              <Row label="Model" value={<code className="font-mono text-xs">{chat.data.model}</code>} />
              {!chat.data.configured && (
                <p className="pt-2 text-xs text-muted-foreground">
                  Set <code className="font-mono">ANTHROPIC_API_KEY</code> in{" "}
                  <code className="font-mono">backend/.env</code> and restart the backend.
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="size-4 text-primary" /> Market data providers
          </CardTitle>
          <CardDescription>
            Which upstream sources are active — keys are managed in backend/.env
          </CardDescription>
        </CardHeader>
        <CardContent>
          {market.isLoading && <Skeleton className="h-24 rounded" />}
          {market.isError && (
            <WidgetError error={market.error} onRetry={() => void market.refetch()} />
          )}
          {market.data && (
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {market.data.providers.map((p) => (
                <div
                  key={p.name}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-2">
                    <Database className="size-4 text-muted-foreground" />
                    <span className="text-sm capitalize">{p.name}</span>
                  </div>
                  <Badge variant={p.configured ? "default" : "secondary"}>
                    {p.configured ? "active" : "no key"}
                  </Badge>
                </div>
              ))}
            </div>
          )}
          {market.data && (
            <p className="mt-3 text-xs text-muted-foreground">
              Cache: {market.data.cache_backend} · scheduler{" "}
              {market.data.scheduler_enabled
                ? `every ${market.data.scheduler_interval_s}s`
                : "off"}{" "}
              · {market.data.tracked_tokens} tracked tokens
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
