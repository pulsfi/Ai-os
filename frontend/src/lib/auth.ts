"use client";

/**
 * API access token store. The token is the shared secret set as
 * API_AUTH_TOKEN on the backend; the user enters it once on the login
 * screen and it's kept in localStorage, sent as X-API-Key on every call.
 */
const KEY = "osai_api_token";

export const authToken = {
  get(): string {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(KEY) ?? "";
  },
  set(token: string): void {
    window.localStorage.setItem(KEY, token);
  },
  clear(): void {
    window.localStorage.removeItem(KEY);
  },
};
