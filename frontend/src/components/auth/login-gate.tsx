"use client";

/**
 * Login gate. When the backend requires an API token, this blocks the app
 * behind a password screen until a valid token is entered. When the
 * backend has no token set (local dev), the check passes and the app
 * renders normally — nothing to log into.
 */
import * as React from "react";
import { Loader2, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { http, ApiError } from "@/lib/api/client";
import { authToken } from "@/lib/auth";

type Status = "checking" | "ok" | "login";

// A protected endpoint: 200 if authed (or auth disabled), 401 if not.
async function verify(): Promise<Status> {
  try {
    await http.get("/system/info");
    return "ok";
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return "login";
    // Network/other error: don't lock the user out — let the app's own
    // error states handle it.
    return "ok";
  }
}

export function LoginGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = React.useState<Status>("checking");
  const [pwd, setPwd] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    verify().then(setStatus);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!pwd.trim()) return;
    setBusy(true);
    setError("");
    authToken.set(pwd.trim());
    const next = await verify();
    if (next === "ok") {
      setStatus("ok");
    } else {
      authToken.clear();
      setError("Wrong password. Try again.");
    }
    setBusy(false);
  }

  if (status === "checking") {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (status === "login") {
    return (
      <div className="flex min-h-dvh items-center justify-center p-4">
        <form
          onSubmit={submit}
          className="w-full max-w-sm space-y-4 rounded-xl border bg-card p-6"
        >
          <div className="flex items-center gap-2">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <Lock className="size-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">OS AI — sign in</h1>
              <p className="text-xs text-muted-foreground">
                Enter your access password to continue
              </p>
            </div>
          </div>
          <Input
            type="password"
            autoFocus
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            placeholder="Access password"
          />
          {error && <p className="text-xs text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy || !pwd.trim()}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : "Unlock"}
          </Button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
