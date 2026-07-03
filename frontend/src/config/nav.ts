/**
 * Navigation model — the single source of truth for the sidebar and any
 * breadcrumb/command-palette built later. Adding a future page (a new agent
 * view, a Solana tool) is one entry here; the shell renders it automatically.
 */
import type { LucideIcon } from "lucide-react";
import {
  Bot,
  Boxes,
  BrainCircuit,
  LayoutDashboard,
  LineChart,
  MessagesSquare,
  Settings,
  TerminalSquare,
} from "lucide-react";

export interface NavItem {
  /** Route href under the (os) group. */
  href: string;
  /** Sidebar label. */
  label: string;
  /** Lucide icon component. */
  icon: LucideIcon;
  /** One-line purpose, used for tooltips/aria. */
  description: string;
}

export const navItems: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    description: "System overview and live metrics",
  },
  {
    href: "/chat",
    label: "AI Chat",
    icon: MessagesSquare,
    description: "Converse with the AI operating system",
  },
  {
    href: "/agents",
    label: "Agents",
    icon: Bot,
    description: "The seven-agent roster and their status",
  },
  {
    href: "/blockchain",
    label: "Blockchain",
    icon: Boxes,
    description: "Live Solana chain data",
  },
  {
    href: "/trading",
    label: "Trading",
    icon: LineChart,
    description: "Market intelligence and paper trading",
  },
  {
    href: "/memory",
    label: "Memory",
    icon: BrainCircuit,
    description: "Long-term system memory and lessons",
  },
  {
    href: "/terminal",
    label: "Terminal",
    icon: TerminalSquare,
    description: "Live logs and command console",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    description: "Configuration and preferences",
  },
];
