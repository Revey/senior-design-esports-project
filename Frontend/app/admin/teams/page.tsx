"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Typeahead from "../Typeahead";
import {
  adminFetch,
  getToken,
  type Player,
  type School,
  type Team,
} from "../adminClient";

type GameFilter = "All" | "Valorant" | "League of Legends";
type Game = "Valorant" | "League of Legends";

type PlayerDraft = { displayName: string; riotId: string; role: string };
const blankPlayer = (): PlayerDraft => ({
  displayName: "",
  riotId: "",
  role: "",
});

type TeamDraft = {
  enabled: boolean;
  name: string;
  tier: string;
  players: PlayerDraft[];
};
const blankTeam = (enabled = false): TeamDraft => ({
  enabled,
  name: "",
  tier: "",
  players: [blankPlayer()],
});

export default function TeamsAdmin() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [teams, setTeams] = useState<Team[]>([]);
  const [query, setQuery] = useState("");
  const [gameFilter, setGameFilter] = useState<GameFilter>("All");
  const [createOpen, setCreateOpen] = useState(false);

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
        <div className="flex items-center justify-between mt-2 mb-6 gap-4 flex-wrap">
          <h1 className="text-2xl font-bold">Teams</h1>
          <button
            onClick={() => setCreateOpen(true)}
            className="px-4 py-2 rounded bg-white text-black font-semibold text-sm hover:bg-white/90"
          >
            + Create Team
          </button>
        </div>

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
              No teams found. Use the Create Team button above, or teams are
              also created automatically when entering a match.
            </p>
          )}
        </div>
      </div>

      {createOpen && (
        <CreateTeamModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            reload();
          }}
        />
      )}
    </main>
  );
}

function TeamRow({ team }: { team: Team }) {
  const [expanded, setExpanded] = useState(false);
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(false);
  const [linkQuery, setLinkQuery] = useState("");

  async function loadPlayers() {
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

  async function unlinkPlayer(playerId: string) {
    await adminFetch(`/api/admin/players/${playerId}/unlink`, {
      method: "PATCH",
      body: JSON.stringify({ teamId: team._id }),
    });
    await loadPlayers();
  }

  async function linkPlayer(player: Player) {
    await adminFetch(`/api/admin/players/${player._id}/link`, {
      method: "PATCH",
      body: JSON.stringify({ teamId: team._id }),
    });
    setLinkQuery("");
    await loadPlayers();
  }

  const searchPlayers = useCallback(
    async (q: string) =>
      adminFetch<Player[]>(
        `/api/admin/players?q=${encodeURIComponent(q)}&limit=15`,
      ),
    [],
  );

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
        <div className="border-t border-white/10 px-4 py-3 space-y-3">
          <div className="text-xs text-white/40 uppercase tracking-wide">
            Roster
          </div>
          {loading && <p className="text-xs text-white/40">Loading…</p>}
          {!loading && players.length === 0 && (
            <p className="text-xs text-white/40">
              No players linked to this team yet.
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
                    className={`text-xs ${
                      p.active ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {p.active ? "active" : "free agent"}
                  </span>
                  <button
                    onClick={() => unlinkPlayer(p._id)}
                    className="ml-auto text-xs px-2 py-0.5 rounded bg-red-600/20 text-red-400 hover:bg-red-600/40"
                  >
                    Unlink
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!loading && (
            <div>
              <div className="text-xs text-white/40 mb-1">Link a player</div>
              <Typeahead<Player>
                placeholder="Search by name or Riot ID…"
                value={linkQuery}
                onChange={setLinkQuery}
                fetcher={searchPlayers}
                render={(pl) =>
                  `${pl.displayName}${pl.riotId ? ` (${pl.riotId})` : ""}${
                    pl.active === false ? " — free agent" : ""
                  }`
                }
                onSelect={linkPlayer}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- Create Team modal ----------

function CreateTeamModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [schoolQ, setSchoolQ] = useState("");
  const [school, setSchool] = useState<School | null>(null);
  const [valTeam, setValTeam] = useState<TeamDraft>(blankTeam(true));
  const [lolTeam, setLolTeam] = useState<TeamDraft>(blankTeam(false));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const fetchSchools = useCallback(
    async (q: string) =>
      adminFetch<School[]>(
        `/api/admin/schools?q=${encodeURIComponent(q)}&limit=10`,
      ),
    [],
  );

  const createSchool = useCallback(
    async (name: string) =>
      adminFetch<School>(`/api/admin/schools`, {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    [],
  );

  async function submit() {
    setError("");
    if (!school) {
      setError("Select or create a school first.");
      return;
    }
    if (!valTeam.enabled && !lolTeam.enabled) {
      setError("Enable at least one team (Valorant or League of Legends).");
      return;
    }
    setSubmitting(true);
    try {
      const drafts: Array<[Game, TeamDraft]> = [
        ["Valorant", valTeam],
        ["League of Legends", lolTeam],
      ];
      for (const [game, draft] of drafts) {
        if (!draft.enabled) continue;
        const teamName = draft.name.trim() || school.name;
        const team = await adminFetch<Team>(`/api/admin/teams`, {
          method: "POST",
          body: JSON.stringify({
            schoolId: school._id,
            name: teamName,
            game,
            tier: draft.tier.trim() || undefined,
          }),
        });
        for (const p of draft.players) {
          const displayName = p.displayName.trim();
          if (!displayName) continue;
          await adminFetch<Player>(`/api/admin/players`, {
            method: "POST",
            body: JSON.stringify({
              displayName,
              riotId: p.riotId.trim() || undefined,
              role: p.role.trim() || undefined,
              teamIds: [team._id],
            }),
          });
        }
      }
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-start justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-3xl bg-neutral-900 rounded-xl border border-white/10 my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-bold">Create Team</h2>
          <button
            onClick={onClose}
            className="text-white/60 hover:text-white text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div>
            <label className="block text-xs text-white/50 mb-1">School</label>
            <Typeahead<School>
              placeholder="Type school name…"
              value={schoolQ}
              onChange={setSchoolQ}
              fetcher={fetchSchools}
              render={(s) => s.name}
              onSelect={(s) => {
                setSchool(s);
                setSchoolQ(s.name);
              }}
              onCreate={createSchool}
              createLabel={(q) => `+ Create school "${q}"`}
            />
            {school && (
              <p className="text-xs text-emerald-400 mt-1">
                Selected: {school.name}
              </p>
            )}
          </div>

          <TeamDraftSection
            game="Valorant"
            school={school}
            draft={valTeam}
            setDraft={setValTeam}
          />
          <TeamDraftSection
            game="League of Legends"
            school={school}
            draft={lolTeam}
            setDraft={setLolTeam}
          />

          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-white/70 hover:text-white"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-5 py-2 rounded bg-white text-black font-semibold text-sm disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function TeamDraftSection({
  game,
  school,
  draft,
  setDraft,
}: {
  game: Game;
  school: School | null;
  draft: TeamDraft;
  setDraft: (d: TeamDraft) => void;
}) {
  const badgeColor =
    game === "Valorant"
      ? "bg-red-500/20 text-red-300"
      : "bg-blue-500/20 text-blue-300";
  const shortLabel = game === "Valorant" ? "VAL" : "LoL";

  function updatePlayer(i: number, patch: Partial<PlayerDraft>) {
    setDraft({
      ...draft,
      players: draft.players.map((p, idx) =>
        idx === i ? { ...p, ...patch } : p,
      ),
    });
  }

  return (
    <div className="rounded-lg border border-white/10 bg-white/5">
      <label className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        <span className="font-medium">Create {game} team</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${badgeColor}`}>
          {shortLabel}
        </span>
      </label>

      {draft.enabled && (
        <div className="border-t border-white/10 px-4 py-4 space-y-4">
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-white/50 mb-1">
                Team name (optional)
              </label>
              <input
                placeholder={school?.name || "defaults to school name"}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              />
            </div>
            <div>
              <label className="block text-xs text-white/50 mb-1">
                Tier (optional)
              </label>
              <input
                placeholder="e.g. Varsity, JV"
                value={draft.tier}
                onChange={(e) => setDraft({ ...draft, tier: e.target.value })}
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-white/50 uppercase tracking-wide">
                Roster (optional)
              </span>
              <button
                type="button"
                onClick={() =>
                  setDraft({
                    ...draft,
                    players: [...draft.players, blankPlayer()],
                  })
                }
                className="text-xs text-emerald-400 hover:text-emerald-300"
              >
                + Add player
              </button>
            </div>
            <div className="space-y-2">
              {draft.players.map((p, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[2fr_2fr_1fr_auto] gap-2 items-center"
                >
                  <input
                    placeholder="Display name"
                    value={p.displayName}
                    onChange={(e) =>
                      updatePlayer(i, { displayName: e.target.value })
                    }
                    className="px-2 py-1.5 rounded bg-black/40 border border-white/20 text-sm"
                  />
                  <input
                    placeholder="Riot IGN#TAG (optional)"
                    value={p.riotId}
                    onChange={(e) =>
                      updatePlayer(i, { riotId: e.target.value })
                    }
                    className="px-2 py-1.5 rounded bg-black/40 border border-white/20 text-sm"
                  />
                  <input
                    placeholder="Role (optional)"
                    value={p.role}
                    onChange={(e) => updatePlayer(i, { role: e.target.value })}
                    className="px-2 py-1.5 rounded bg-black/40 border border-white/20 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        players:
                          draft.players.length > 1
                            ? draft.players.filter((_, idx) => idx !== i)
                            : [blankPlayer()],
                      })
                    }
                    className="text-red-400 hover:text-red-300 text-sm px-2"
                    aria-label="Remove player"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <p className="text-xs text-white/40 mt-2">
              Rows with an empty display name are skipped.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
