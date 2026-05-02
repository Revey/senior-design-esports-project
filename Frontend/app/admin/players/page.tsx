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

const PAGE_SIZE = 10;

export default function PlayersAdmin() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [players, setPlayers] = useState<Player[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [newName, setNewName] = useState("");
  const [newRiot, setNewRiot] = useState("");
  const [newRole, setNewRole] = useState("");
  const [newGame, setNewGame] = useState<"valorant" | "lol">("valorant");

  useEffect(() => {
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router]);

  // Reset to page 1 on new search.
  useEffect(() => {
    setPage(1);
  }, [query]);

  const reload = useCallback(async () => {
    const params = new URLSearchParams({
      q: query,
      limit: String(PAGE_SIZE),
      skip: String((page - 1) * PAGE_SIZE),
      paginated: "true",
    });
    const data = await adminFetch<{ items: Player[]; total: number }>(
      `/api/admin/players?${params}`,
    );
    setPlayers(data.items);
    setTotal(data.total);
  }, [query, page]);

  useEffect(() => {
    if (ready) reload();
  }, [ready, reload]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function createPlayer() {
    if (!newName.trim()) return;
    await adminFetch("/api/admin/players", {
      method: "POST",
      body: JSON.stringify({
        displayName: newName.trim(),
        game: newGame,
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
            leaderboard data. Pick the game so the player record is created
            in the correct context — link them to teams below.
          </p>
          <div className="grid sm:grid-cols-5 gap-2">
            <input
              placeholder="Display name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="px-3 py-2 rounded bg-black/40 border border-white/20"
            />
            <select
              value={newGame}
              onChange={(e) => setNewGame(e.target.value as "valorant" | "lol")}
              className="px-3 py-2 rounded bg-black/40 border border-white/20"
            >
              <option value="valorant">Valorant</option>
              <option value="lol">League of Legends</option>
            </select>
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

        {total > 0 && (
          <Pagination
            page={page}
            pageCount={pageCount}
            total={total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        )}
      </div>
    </main>
  );
}

function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  pageCount: number;
  total: number;
  pageSize: number;
  onPageChange: (p: number) => void;
}) {
  const windowSize = 5;
  const start = Math.max(1, Math.min(page - 2, pageCount - windowSize + 1));
  const end = Math.min(pageCount, start + windowSize - 1);
  const pages: number[] = [];
  for (let i = start; i <= end; i++) pages.push(i);

  const shownFrom = (page - 1) * pageSize + 1;
  const shownTo = Math.min(page * pageSize, total);

  return (
    <div className="mt-6 flex items-center justify-between text-sm text-white/60">
      <span>
        Showing {shownFrom}–{shownTo} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
          className="px-2 py-1 rounded border border-white/15 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ‹
        </button>
        {start > 1 && (
          <>
            <PageBtn n={1} active={page === 1} onClick={onPageChange} />
            {start > 2 && <span className="px-1 text-white/30">…</span>}
          </>
        )}
        {pages.map((n) => (
          <PageBtn key={n} n={n} active={n === page} onClick={onPageChange} />
        ))}
        {end < pageCount && (
          <>
            {end < pageCount - 1 && <span className="px-1 text-white/30">…</span>}
            <PageBtn
              n={pageCount}
              active={page === pageCount}
              onClick={onPageChange}
            />
          </>
        )}
        <button
          disabled={page === pageCount}
          onClick={() => onPageChange(page + 1)}
          className="px-2 py-1 rounded border border-white/15 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ›
        </button>
      </div>
    </div>
  );
}

function PageBtn({
  n,
  active,
  onClick,
}: {
  n: number;
  active: boolean;
  onClick: (p: number) => void;
}) {
  return (
    <button
      onClick={() => onClick(n)}
      className={`min-w-[32px] px-2 py-1 rounded border text-sm ${
        active
          ? "bg-white text-black border-white font-semibold"
          : "border-white/15 hover:bg-white/5"
      }`}
    >
      {n}
    </button>
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
                {t.teamName} ({t.game === "valorant" ? "VAL" : "LoL"})
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
              `${t.teamName} — ${t.school} (${t.game === "valorant" ? "VAL" : "LoL"})`
            }
            onSelect={link}
          />
        </div>
      </div>
    </div>
  );
}

