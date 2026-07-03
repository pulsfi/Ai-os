"use client";

/**
 * Single composition point for all client-side providers, mounted once in the
 * root layout. Order: theme (outermost, sets the class) → query → tooltips,
 * with the global toaster alongside.
 */
import type { ReactNode } from "react";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryProvider } from "./query-provider";
import { ThemeProvider } from "./theme-provider";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      <QueryProvider>
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        <Toaster position="top-right" richColors closeButton />
      </QueryProvider>
    </ThemeProvider>
  );
}
