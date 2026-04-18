"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminFetch, clearToken, getToken } from "./adminClient";

type RecentMatch = {
  _id: string;
  game: string;
  team1Name?: string;
  team2Name?: string;
  team1Score?: number;
  team2Score?: number;
  format?: string;
  date?: string;
};

type AdminStats = {
  counts: {
    matches: number;
    players: number;
    teams: number;
    schools: number;
    organizations: number;
    conferences: number;
  };
  recent_matches: RecentMatch[];
};

export default function AdminHome() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }
    adminFetch("/api/admin/me")
      .then(() => setReady(true))
      .catch(() => router.replace("/admin/login"));
  }, [router]);

  useEffect(() => {
    if (!ready) return;
    adminFetch<AdminStats>("/api/admin/stats")
      .then(setStats)
      .catch((e: Error) => setError(e.message));
  }, [ready]);

  if (!ready) return null;

  const countTiles: { label: string; key: keyof AdminStats["counts"] }[] = [
    { label: "Matches", key: "matches" },
    { label: "Players", key: "players" },
    { label: "Teams", key: "teams" },
    { label: "Schools", key: "schools" },
    { label: "Orgs", key: "organizations" },
    { label: "Conferences", key: "conferences" },
  ];

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <button
            onClick={() => {
              clearToken();
              router.push("/admin/login");
            }}
            className="text-sm text-white/60 hover:text-white"
          >
            Sign out
          </button>
        </div>

        {/* Stats tiles */}
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 mb-8">
          {countTiles.map((t) => (
            <div key={t.key} className="p-4 rounded-lg border border-white/10 bg-white/5">
              <div className="text-xs uppercase tracking-wider text-white/50">{t.label}</div>
              <div className="text-2xl font-bold tabular-nums mt-1">
                {stats ? stats.counts[t.key] : <span className="text-white/30">—</span>}
              </div>
            </div>
          ))}
        </div>

        {/* Recent matches */}
        <section className="mb-8 p-5 rounded-xl border border-white/10 bg-white/5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm uppercase tracking-wider text-white/60">Recent matches</h2>
            <Link href="/admin/matches" className="text-xs text-white/60 hover:text-white">
              Manage all →
            </Link>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          {!stats && !error && <p className="text-white/40 text-sm">Loading…</p>}
          {stats && stats.recent_matches.length === 0 && (
            <p className="text-white/40 text-sm">No matches entered yet.</p>
          )}
          {stats && stats.recent_matches.length > 0 && (
            <ul className="divide-y divide-white/5">
              {stats.recent_matches.map((m) => (
                <li key={m._id} className="py-2 flex items-center justify-between text-sm">
                  <div>
                    <span className="font-medium">{m.team1Name}</span>
                    <span className="text-white/40 mx-2">
                      {m.team1Score}–{m.team2Score}
                    </span>
                    <span className="font-medium">{m.team2Name}</span>
                  </div>
                  <div className="text-white/50 text-xs">
                    {m.game === "Valorant" ? "VAL" : "LoL"} · {m.format} ·{" "}
                    {m.date ? new Date(m.date).toLocaleDateString() : "—"}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Action tiles */}
        <div className="grid sm:grid-cols-2 gap-4">
          <Link
            href="/admin/match"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Enter Match</div>
            <div className="text-sm text-white/60 mt-1">
              Upload post-game stats for Valorant or League of Legends.
            </div>
          </Link>
          <Link
            href="/admin/matches"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Manage Matches</div>
            <div className="text-sm text-white/60 mt-1">
              Edit scores or delete mis-entered series.
            </div>
          </Link>
          <Link
            href="/admin/players"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Manage Players</div>
            <div className="text-sm text-white/60 mt-1">
              Create, link, and unlink players from teams.
            </div>
          </Link>
          <Link
            href="/admin/teams"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Manage Teams</div>
            <div className="text-sm text-white/60 mt-1">
              View teams, their records, rosters, and conference memberships.
            </div>
          </Link>
          <Link
            href="/admin/leagues"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Manage Leagues</div>
            <div className="text-sm text-white/60 mt-1">
              Organizations, seasons (Fall / Spring), and conferences / divisions.
            </div>
          </Link>
        </div>
      </div>
    </main>
  );
}
