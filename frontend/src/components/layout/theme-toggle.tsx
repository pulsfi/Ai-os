"use client";

/**
 * Light/dark toggle. Icon visibility is driven purely by the `.dark` class
 * (via Tailwind's dark variant), so there is no hydration mismatch and no
 * mount-guard effect — the correct icon is chosen by CSS on first paint.
 * The click handler reads the resolved theme, which is available by the time
 * a user can interact.
 */
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      <Sun className="size-5 dark:hidden" />
      <Moon className="hidden size-5 dark:block" />
    </Button>
  );
}
