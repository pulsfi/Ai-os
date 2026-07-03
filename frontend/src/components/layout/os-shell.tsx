/**
 * The OS application shell: fixed sidebar + sticky top nav + scrollable main.
 * Wraps every page in the (os) route group. Server component — it only
 * composes client pieces, so it stays out of the client bundle itself.
 */
import type { ReactNode } from "react";

import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";

export function OsShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl p-4 md:p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
