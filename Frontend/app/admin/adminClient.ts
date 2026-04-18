"use client";

const RAW_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export const API_BASE = RAW_BASE.replace(/\/$/, "");

const TOKEN_KEY = "admin_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function adminFetch<T = unknown>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(opts.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      const returnTo = window.location.pathname + window.location.search;
      sessionStorage.setItem("admin_return", returnTo);
      alert("Your session has expired — please log in again.");
      window.location.href = "/admin/login";
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export type School = { _id: string; name: string; slug: string };
export type Team = {
  _id: string;
  teamName: string;
  slug: string;
  school: string;
  schoolId?: string;
  game: "Valorant" | "League of Legends";
  tier?: string | null;
  wins?: number;
  losses?: number;
};
export type Player = {
  _id: string;
  displayName: string;
  riotId?: string | null;
  role?: string | null;
  teamIds?: string[];
  active?: boolean;
};

export type Game = "Valorant" | "League of Legends";
export type Semester = "Fall" | "Spring";
export type ConfKind = "regional" | "division" | "partner" | "tier";

export type Organization = {
  _id: string;
  name: string;
  abbreviation: string;
  slug: string;
  games: Game[];
};

export type Season = {
  _id: string;
  orgId: string;
  year: string; // "2025-2026"
  semester: Semester;
  label: string; // "CVAL Fall 2025"
  active: boolean;
};

export type Conference = {
  _id: string;
  orgId: string;
  name: string;
  shortName: string;
  slug: string;
  tier?: string | null;
  kind: ConfKind;
};

export type LeagueTreeOrg = Organization & {
  seasons: Season[];
  conferences: Conference[];
};

export type Membership = {
  _id: string;
  teamId: string;
  conferenceId: string;
  seasonId: string;
  active: boolean;
  seasonLabel?: string;
  conferenceName?: string;
  conferenceTier?: string | null;
  orgAbbreviation?: string;
  teamName?: string;
};
