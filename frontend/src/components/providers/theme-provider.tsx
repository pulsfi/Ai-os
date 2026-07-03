"use client";

/**
 * next-themes wrapper. Dark is the default for the AI OS; the class strategy
 * toggles the `.dark` variables defined in globals.css.
 */
import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

export function ThemeProvider({
  children,
  ...props
}: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
