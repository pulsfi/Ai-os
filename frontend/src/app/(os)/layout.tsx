import type { ReactNode } from "react";

import { OsShell } from "@/components/layout/os-shell";

/** Every page in the (os) group renders inside the app shell. */
export default function OsGroupLayout({ children }: { children: ReactNode }) {
  return <OsShell>{children}</OsShell>;
}
