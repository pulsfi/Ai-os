import type { ReactNode } from "react";

import { LoginGate } from "@/components/auth/login-gate";
import { OsShell } from "@/components/layout/os-shell";

/** Every page in the (os) group renders inside the app shell, behind the
 *  login gate (no-op when the backend has no auth token configured). */
export default function OsGroupLayout({ children }: { children: ReactNode }) {
  return (
    <LoginGate>
      <OsShell>{children}</OsShell>
    </LoginGate>
  );
}
