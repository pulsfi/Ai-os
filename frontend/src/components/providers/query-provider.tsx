"use client";

/**
 * TanStack Query provider. The client is created once per browser session via
 * useState so it survives re-renders but never leaks between requests on the
 * server. Defaults tuned for a live dashboard: short stale time, no refetch
 * storms, one retry.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
