/**
 * Navigation model — the single source of truth for the sidebar.
 * The institutional terminal's eight sections.
 */
import type { LucideIcon } from "lucide-react";
import {
  Crosshair,
  History,
  LayoutDashboard,
  Radar,
  Settings,
  Wallet,
  Waypoints,
  Workflow,
  FlaskConical,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, description: "Live command center" },
  { href: "/scanner", label: "Live Scanner", icon: Radar, description: "New launches, live" },
  { href: "/sniper", label: "Launch Sniper", icon: Crosshair, description: "Scored auto-entries" },
  { href: "/smart-money", label: "Smart Money", icon: Waypoints, description: "Wallet & flow activity" },
  { href: "/portfolio", label: "Portfolio", icon: Wallet, description: "Positions, PnL, trades" },
  { href: "/research", label: "Research", icon: FlaskConical, description: "Inspect & score any token" },
  { href: "/automation", label: "Automation", icon: Workflow, description: "Bots & agent pipeline" },
  { href: "/backtest", label: "Backtesting", icon: History, description: "Replay & validate strategies" },
  { href: "/settings", label: "Settings", icon: Settings, description: "Config & providers" },
];
