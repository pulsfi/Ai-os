/**
 * Global UI state (client-only): sidebar collapse + mobile drawer.
 *
 * Zustand is used for cross-component UI state that isn't server data
 * (server data belongs to TanStack Query). Kept intentionally small.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UiState {
  /** Desktop rail collapsed to icons only. Persisted across sessions. */
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;

  /** Mobile drawer open. Not persisted (always closed on load). */
  mobileNavOpen: boolean;
  setMobileNavOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      mobileNavOpen: false,
      setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
    }),
    {
      name: "ai-os-ui",
      // Only the desktop preference is worth persisting.
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }),
    },
  ),
);
