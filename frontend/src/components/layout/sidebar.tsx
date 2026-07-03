"use client";

/**
 * Desktop sidebar rail. Fixed-width, collapsible to an icon rail. Hidden below
 * the `lg` breakpoint, where the mobile drawer (in the top nav) takes over.
 */
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useUiStore } from "@/stores/ui-store";
import { cn } from "@/lib/utils";
import { Brand } from "./brand";
import { SidebarNav } from "./sidebar-nav";

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);

  return (
    <aside
      data-collapsed={collapsed}
      className={cn(
        "hidden lg:flex lg:flex-col shrink-0 border-r border-sidebar-border bg-sidebar",
        "transition-[width] duration-200 ease-in-out",
        collapsed ? "w-[68px]" : "w-64",
      )}
    >
      <div className="flex h-14 items-center px-2">
        <Brand collapsed={collapsed} />
      </div>
      <Separator className="bg-sidebar-border" />

      <ScrollArea className="flex-1 py-3">
        <SidebarNav collapsed={collapsed} />
      </ScrollArea>

      <Separator className="bg-sidebar-border" />
      <div className={cn("p-2", collapsed && "flex justify-center")}>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="text-sidebar-foreground/70"
        >
          {collapsed ? (
            <PanelLeftOpen className="size-5" />
          ) : (
            <PanelLeftClose className="size-5" />
          )}
        </Button>
      </div>
    </aside>
  );
}
