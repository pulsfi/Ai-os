"use client";

/**
 * Top navigation bar. Shows the mobile menu trigger, the active section title
 * (derived from the route), and global actions (theme toggle, account stub).
 * Sticky so it stays put while the page scrolls.
 */
import { usePathname } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { navItems } from "@/config/nav";
import { MobileNav } from "./mobile-nav";
import { ThemeToggle } from "./theme-toggle";

function useSectionTitle() {
  const pathname = usePathname();
  const match = navItems.find(
    (i) => pathname === i.href || pathname.startsWith(`${i.href}/`),
  );
  return match?.label ?? "AI OS";
}

export function TopNav() {
  const title = useSectionTitle();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <MobileNav />
      <h1 className="text-sm font-semibold tracking-tight">{title}</h1>

      <div className="ml-auto flex items-center gap-1">
        <ThemeToggle />
        <Button
          variant="ghost"
          size="icon"
          className="rounded-full"
          aria-label="Account"
        >
          <Avatar className="size-7">
            <AvatarFallback className="bg-primary/15 text-xs text-primary">
              OS
            </AvatarFallback>
          </Avatar>
        </Button>
      </div>
    </header>
  );
}
