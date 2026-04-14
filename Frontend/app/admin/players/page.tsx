"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Typeahead from "../Typeahead";
import {
  adminFetch,
  getToken,
  type Player,
  type Team,
} from "../adminClient";

export default function PlayersAdmin() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [players, setPlayers] = useState<Player[]>([]);
  const [query, setQuery] = useState("");
  const [newName, setNewName] = useState("");
  const [newRiot, setNewRiot] = useState("");
  const [newRole, setNewRole] = useState("");

  useEffect(() => {
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router]);

  const reload = useCallback(async () => {
    const data = await adminFetch<Player[]>(
      `/api/admin/players?q=${encodeURIComponent(query)}&limit=100`,
    );
    setPlayers(data);
  }, [query]);

  useEffect(() => {
    if (ready) reload();
  }, [ready, reload]);

  async function createPlayer() {
    if (!newName.trim()) return;
    await adminFetch("/api/admin/players", {
      method: "POST",
      body: JSON.stringify({
        displayName: newName.trim(),
        riotId: newRiot.trim() || null,
        role: newRole.trim() || null,
        teamIds: [],
      }),
    });
    setNewName("");
    setNewRiot("");
    setNewRole("");
    await reload();
  }

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <Link href="/admin" className="text-sm text-white/60 hover:text-white">
          ← Back
        </Link>
        <h1 className="text-2xl font-bold mt-2 mb-6">Players</h1>

        <section className="mb-8 p-5 rounded-xl border border-white/10 bg-white/5">
          <h2 className="font-semibold mb-1">Create Player</h2>
          <p className="text-xs text-white/40 mb-3">
            Players here are admin-entered and separate from the public
            leaderboard data. A player&apos;s game (Valorant or LoL) is
            determined by the team(s) you link them to.
          </p>
          <div className="grid sm:grid-cols-4 gap-2">
            <input
              placeholder="Display name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="px-3 py-2 rounded bg-black/40 border border-white/20"
            />
            <input
              placeholder="Riot ID (Name#TAG)"
              value={newRiot}
              onChange={(e) => setNewRiot(e.target.value)}
              className="px-3 py-2 rounded bg-black/40 border border-white/20"
            />
            <input
              placeholder="Role"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="px-3 py-2 rounded bg-black/40 border border-white/20"
            />
            <button
              onClick={createPlayer}
              className="rounded bg-white text-black font-medium"
            >
              Create
            </button>
          </div>
        </section>

        <div className="mb-4">
          <input
            placeholder="Search players…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
          />
        </div>

        <div className="space-y-3">
          {players.map((p) => (
            <PlayerRow key={p._id} player={p} onChanged={reload} />
          ))}
          {players.length === 0 && (
            <p className="text-white/50 text-sm">
              No players found. Players in this system are manually entered —
              they are separate from the public leaderboard data. Create a
              player above and link them to a team.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}

function PlayerRow({
  player,
  onChanged,
}: {
  player: Player;
  onChanged: () => void | Promise<void>;
}) {
  const [teamQuery, setTeamQuery] = useState("");
  const [currentTeams, setCurrentTeams] = useState<Team[]>([]);

  const loadTeams = useCallback(async () => {
    if (!player.teamIds || player.teamIds.length === 0) {
      setCurrentTeams([]);
      return;
    }
    const all = await adminFetch<Team[]>(`/api/admin/teams?limit=200`);
    setCurrentTeams(all.filter((t) => player.teamIds?.includes(t._id)));
  }, [player]);

  useEffect(() => {
    loadTeams();
  }, [loadTeams]);

  async function link(team: Team) {
    await adminFetch(`/api/admin/players/${player._id}/link`, {
      method: "PATCH",
      body: JSON.stringify({ teamId: team._id }),
    });
    setTeamQuery("");
    await onChanged();
  }

  async function unlink(teamId: string) {
    await adminFetch(`/api/admin/players/${player._id}/unlink`, {
      method: "PATCH",
      body: JSON.stringify({ teamId }),
    });
    await onChanged();
  }

  return (
    <div className="p-4 rounded-lg border border-white/10 bg-white/5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-medium">{player.displayName}</div>
          <div className="text-xs text-white/50">
            {player.riotId || "—"} · {player.role || "—"} ·{" "}
            {player.active ? (
              <span className="text-emerald-400">active</span>
            ) : (
              <span className="text-amber-400">free agent</span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {currentTeams.map((t) => (
              <span
                key={t._id}
                className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-white/10 text-xs"
              >
                {t.teamName} ({t.game === "Valorant" ? "VAL" : "LoL"})
                <button
                  onClick={() => unlink(t._id)}
                  className="text-red-300 hover:text-red-400"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
        <div className="w-72">
          <Typeahead<Team>
            placeholder="Link to team…"
            value={teamQuery}
            onChange={setTeamQuery}
            fetcher={async (q) =>
              adminFetch<Team[]>(
                `/api/admin/teams?q=${encodeURIComponent(q)}&limit=15`,
              )
            }
            render={(t) =>
              `${t.teamName} — ${t.school} (${t.game === "Valorant" ? "VAL" : "LoL"})`
            }
            onSelect={link}
          />
        </div>
      </div>
    </div>
  );
}

