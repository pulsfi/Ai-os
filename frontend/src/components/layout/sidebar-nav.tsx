"use client";

/**
 * The navigation list shared by the desktop rail and the mobile drawer.
 * Active state is derived from the pathname (prefix match so nested routes
 * keep their parent highlighted). Collapsed mode shows icons + tooltips.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { navItems } from "@/config/nav";
import { cn } from "@/lib/utils";

interface SidebarNavProps {
  collapsed?: boolean;
  /** Called after a link is chosen — used to close the mobile drawer. */
  onNavigate?: () => void;
}

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 px-2" aria-label="Primary">
      {navItems.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;

        const link = (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              active &&
                "bg-sidebar-accent text-sidebar-foreground glow-primary",
              collapsed && "justify-center px-0",
            )}
          >
            <Icon
              className={cn(
                "size-5 shrink-0 transition-colors",
                active
                  ? "text-sidebar-primary"
                  : "text-sidebar-foreground/60 group-hover:text-sidebar-foreground",
              )}
            />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </Link>
        );

        // In collapsed mode the label lives in a tooltip.
        return collapsed ? (
          <Tooltip key={item.href}>
            <TooltipTrigger asChild>{link}</TooltipTrigger>
            <TooltipContent side="right">{item.label}</TooltipContent>
          </Tooltip>
        ) : (
          link
        );
      })}
    </nav>
  );
}
