"use client";

/**
 * Mobile navigation drawer. Reuses SidebarNav inside a shadcn Sheet, driven by
 * the shared UI store so the top-nav trigger and the drawer stay in sync.
 */
import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useUiStore } from "@/stores/ui-store";
import { Brand } from "./brand";
import { SidebarNav } from "./sidebar-nav";

export function MobileNav() {
  const open = useUiStore((s) => s.mobileNavOpen);
  const setOpen = useUiStore((s) => s.setMobileNavOpen);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild className="lg:hidden">
        <Button variant="ghost" size="icon" aria-label="Open navigation">
          <Menu className="size-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 border-sidebar-border bg-sidebar p-0">
        <SheetHeader className="h-14 justify-center px-2">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <Brand />
        </SheetHeader>
        <Separator className="bg-sidebar-border" />
        <ScrollArea className="h-[calc(100vh-3.5rem)] py-3">
          <SidebarNav onNavigate={() => setOpen(false)} />
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
