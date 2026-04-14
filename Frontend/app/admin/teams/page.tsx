"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { adminFetch, getToken, type Player, type Team } from "../adminClient";

type GameFilter = "All" | "Valorant" | "League of Legends";

export default function TeamsAdmin() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [teams, setTeams] = useState<Team[]>([]);
  const [query, setQuery] = useState("");
  const [gameFilter, setGameFilter] = useState<GameFilter>("All");

  useEffect(() => {
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router]);

  const reload = useCallback(async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    if (gameFilter !== "All") params.set("game", gameFilter);
    const data = await adminFetch<Team[]>(`/api/admin/teams?${params}`);
    setTeams(data);
  }, [query, gameFilter]);

  useEffect(() => {
    if (ready) reload();
  }, [ready, reload]);

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <Link href="/admin" className="text-sm text-white/60 hover:text-white">
          ← Back
        </Link>
        <h1 className="text-2xl font-bold mt-2 mb-6">Teams</h1>

        <div className="flex flex-wrap gap-3 mb-4">
          <input
            placeholder="Search teams…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 min-w-[200px] px-3 py-2 rounded bg-black/40 border border-white/20"
          />
          <div className="flex rounded overflow-hidden border border-white/20">
            {(["All", "Valorant", "League of Legends"] as GameFilter[]).map(
              (g) => (
                <button
                  key={g}
                  onClick={() => setGameFilter(g)}
                  className={`px-3 py-2 text-sm transition ${
                    gameFilter === g
                      ? "bg-white text-black font-semibold"
                      : "bg-black/40 text-white/60 hover:text-white"
                  }`}
                >
                  {g === "League of Legends" ? "LoL" : g}
                </button>
              ),
            )}
          </div>
        </div>

        <div className="space-y-3">
          {teams.map((t) => (
            <TeamRow key={t._id} team={t} />
          ))}
          {teams.length === 0 && (
            <p className="text-white/50 text-sm">
              No teams found. Teams are created automatically when entering a
              match — use the Enter Match page to add new teams.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}

function TeamRow({ team }: { team: Team }) {
  const [expanded, setExpanded] = useState(false);
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(false);

  async function loadPlayers() {
    if (players.length > 0) return; // already loaded
    setLoading(true);
    try {
      const data = await adminFetch<Player[]>(
        `/api/admin/players?teamId=${team._id}&limit=100`,
      );
      setPlayers(data);
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    if (!expanded) loadPlayers();
    setExpanded((v) => !v);
  }

  const gameLabel = team.game === "Valorant" ? "VAL" : "LoL";
  const gameBadgeColor =
    team.game === "Valorant" ? "bg-red-500/20 text-red-300" : "bg-blue-500/20 text-blue-300";

  return (
    <div className="rounded-lg border border-white/10 bg-white/5 overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition"
      >
        <div className="flex items-center gap-3 flex-wrap">
          <span className="font-medium">{team.teamName}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${gameBadgeColor}`}>
            {gameLabel}
          </span>
          {team.tier && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/60">
              {team.tier}
            </span>
          )}
          <span className="text-xs text-white/40">{team.school}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-4">
          <span className="text-xs text-white/50">
            W{team.wins ?? 0}–L{team.losses ?? 0}
          </span>
          <span className="text-white/40 text-sm">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-white/10 px-4 py-3">
          <div className="text-xs text-white/40 mb-2 uppercase tracking-wide">
            Roster
          </div>
          {loading && <p className="text-xs text-white/40">Loading…</p>}
          {!loading && players.length === 0 && (
            <p className="text-xs text-white/40">
              No players linked to this team yet. Use Manage Players to link
              players.
            </p>
          )}
          {!loading && players.length > 0 && (
            <ul className="space-y-1">
              {players.map((p) => (
                <li key={p._id} className="flex items-center gap-3 text-sm">
                  <span className="font-medium">{p.displayName}</span>
                  {p.riotId && (
                    <span className="text-white/40 text-xs">{p.riotId}</span>
                  )}
                  {p.role && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/60">
                      {p.role}
                    </span>
                  )}
                  <span
                    className={`text-xs ml-auto ${
                      p.active ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {p.active ? "active" : "free agent"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
