"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Typeahead from "../Typeahead";
import {
  adminFetch,
  getToken,
  type Conference,
  type Membership,
  type Organization,
  type Player,
  type School,
  type Season,
  type Team,
} from "../adminClient";

type GameFilter = "All" | "Valorant" | "League of Legends";
type Game = "valorant" | "lol";

export default function TeamsAdmin() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [teams, setTeams] = useState<Team[]>([]);
  const [query, setQuery] = useState("");
  const [gameFilter, setGameFilter] = useState<GameFilter>("All");
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router]);

  const reload = useCallback(async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    if (gameFilter !== "All") params.set("game", gameFilter === "Valorant" ? "valorant" : "lol");
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
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded bg-white text-black text-sm font-semibold hover:bg-white/90"
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
                  {g === "League of Legends" ? "LoL" : g === "Valorant" ? "VAL" : g}
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
              No teams found. Use “+ Create Team” to add one, or the Enter
              Match page to create teams on the fly.
            </p>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateTeamModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            reload();
          }}
        />
      )}
    </main>
  );
}

// ---------- Create Team modal ----------

type PlayerRow = {
  displayName: string;
  riotId: string;
  role: string;
};

const blankPlayer = (): PlayerRow => ({
  displayName: "",
  riotId: "",
  role: "",
});

function CreateTeamModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [schoolQ, setSchoolQ] = useState("");
  const [school, setSchool] = useState<School | null>(null);
  const [teamName, setTeamName] = useState("");
  const [game, setGame] = useState<Game>("valorant");
  const [players, setPlayers] = useState<PlayerRow[]>([blankPlayer()]);
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

  function setPlayer(i: number, patch: Partial<PlayerRow>) {
    setPlayers((prev) =>
      prev.map((p, idx) => (idx === i ? { ...p, ...patch } : p)),
    );
  }

  function addPlayer() {
    setPlayers((prev) => [...prev, blankPlayer()]);
  }

  function removePlayer(i: number) {
    setPlayers((prev) =>
      prev.length === 1 ? [blankPlayer()] : prev.filter((_, idx) => idx !== i),
    );
  }

  async function submit() {
    setError("");
    if (!school) {
      setError("Select or create a school first.");
      return;
    }
    setSubmitting(true);
    try {
      const finalName = teamName.trim() || school.name;
      const team = await adminFetch<Team>(`/api/admin/teams`, {
        method: "POST",
        body: JSON.stringify({
          schoolId: school._id,
          name: finalName,
          game,
        }),
      });
      const validPlayers = players.filter((p) => p.displayName.trim());
      for (const p of validPlayers) {
        await adminFetch(`/api/admin/players`, {
          method: "POST",
          body: JSON.stringify({
            displayName: p.displayName.trim(),
            riotId: p.riotId.trim() || null,
            role: p.role.trim() || null,
            teamIds: [team._id],
          }),
        });
      }
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create team");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-30 bg-black/70 flex items-start justify-center overflow-y-auto py-10 px-4">
      <div className="w-full max-w-xl rounded-lg border border-white/15 bg-neutral-900 p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Create Team</h2>
          <button
            onClick={onClose}
            className="text-white/60 hover:text-white text-2xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-white/50 mb-1">
              School *
            </label>
            <Typeahead<School>
              placeholder="School name…"
              value={schoolQ}
              onChange={(v) => {
                setSchoolQ(v);
                if (school && v !== school.name) setSchool(null);
              }}
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

          <div>
            <label className="block text-xs text-white/50 mb-1">
              Team name (optional — defaults to school name)
            </label>
            <input
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder={school?.name || "Team name"}
              className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
            />
          </div>

          <div>
            <label className="block text-xs text-white/50 mb-1">Game *</label>
            <select
              value={game}
              onChange={(e) => setGame(e.target.value as Game)}
              className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
            >
              <option value="valorant">Valorant</option>
              <option value="lol">League of Legends</option>
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-white/50">
                Roster (optional) — adds to {game === "valorant" ? "Valorant" : "LoL"} roster
              </label>
              <button
                type="button"
                onClick={addPlayer}
                className="text-xs text-emerald-400 hover:text-emerald-300"
              >
                + Add player
              </button>
            </div>
            <div className="space-y-2">
              {players.map((p, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[1fr_1fr_110px_auto] gap-2 items-center"
                >
                  <input
                    placeholder="Display name"
                    value={p.displayName}
                    onChange={(e) =>
                      setPlayer(i, { displayName: e.target.value })
                    }
                    className="px-2 py-1.5 text-sm rounded bg-black/40 border border-white/20"
                  />
                  <input
                    placeholder="Riot IGN#Tag"
                    value={p.riotId}
                    onChange={(e) => setPlayer(i, { riotId: e.target.value })}
                    className="px-2 py-1.5 text-sm rounded bg-black/40 border border-white/20"
                  />
                  <input
                    placeholder="Role"
                    value={p.role}
                    onChange={(e) => setPlayer(i, { role: e.target.value })}
                    className="px-2 py-1.5 text-sm rounded bg-black/40 border border-white/20"
                  />
                  <button
                    type="button"
                    onClick={() => removePlayer(i)}
                    className="text-red-400 hover:text-red-300 text-lg leading-none px-2"
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

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded border border-white/20 text-sm hover:bg-white/5"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={submitting || !school}
              className="px-4 py-2 rounded bg-white text-black text-sm font-semibold hover:bg-white/90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting ? "Creating…" : "Create team"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- existing team row ----------

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

  const gameLabel = team.game === "valorant" ? "VAL" : "LoL";
  const gameBadgeColor =
    team.game === "valorant" ? "bg-red-500/20 text-red-300" : "bg-blue-500/20 text-blue-300";

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

          <MembershipsSection teamId={team._id} teamGame={team.game} />
        </div>
      )}
    </div>
  );
}

// ---------- team memberships (conference + season per semester) ----------

function MembershipsSection({
  teamId,
  teamGame,
}: {
  teamId: string;
  teamGame: "valorant" | "lol";
}) {
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [m, o] = await Promise.all([
        adminFetch<Membership[]>(`/api/admin/memberships?teamId=${teamId}`),
        adminFetch<Organization[]>(
          `/api/admin/orgs?game=${encodeURIComponent(teamGame)}&limit=100`,
        ),
      ]);
      setMemberships(m);
      setOrgs(o);
    } finally {
      setLoading(false);
    }
  }, [teamId, teamGame]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function toggleActive(m: Membership) {
    await adminFetch(`/api/admin/memberships/${m._id}`, {
      method: "PATCH",
      body: JSON.stringify({ active: !m.active }),
    });
    await reload();
  }

  async function removeMembership(m: Membership) {
    if (
      !confirm(
        `Remove ${m.orgAbbreviation || ""} ${m.conferenceName || ""} ${m.seasonLabel || ""} membership?`,
      )
    )
      return;
    await adminFetch(`/api/admin/memberships/${m._id}`, { method: "DELETE" });
    await reload();
  }

  return (
    <div className="pt-3 border-t border-white/10">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs text-white/40 uppercase tracking-wide">
          Conference / Division memberships
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="text-xs text-emerald-400 hover:text-emerald-300"
        >
          + Add membership
        </button>
      </div>

      {loading && <p className="text-xs text-white/40">Loading…</p>}
      {!loading && memberships.length === 0 && (
        <p className="text-xs text-white/40">
          Not enrolled in any conferences yet.
        </p>
      )}
      {!loading && memberships.length > 0 && (
        <ul className="space-y-1">
          {memberships.map((m) => (
            <li key={m._id} className="flex items-center gap-2 text-sm py-1">
              <span className="font-medium">{m.orgAbbreviation}</span>
              <span className="text-white/70">
                {m.conferenceTier ? `${m.conferenceTier} · ` : ""}
                {m.conferenceName}
              </span>
              <span className="text-xs text-white/40">{m.seasonLabel}</span>
              <button
                onClick={() => toggleActive(m)}
                className={`text-xs px-2 py-0.5 rounded-full ${
                  m.active
                    ? "bg-emerald-500/30 text-emerald-300"
                    : "bg-white/10 text-white/50 hover:bg-white/20"
                }`}
              >
                {m.active ? "active" : "inactive"}
              </button>
              <button
                onClick={() => removeMembership(m)}
                className="ml-auto text-xs px-2 py-0.5 rounded bg-red-600/20 text-red-400 hover:bg-red-600/40"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {showAdd && (
        <AddMembershipForm
          teamId={teamId}
          orgs={orgs}
          onClose={() => setShowAdd(false)}
          onAdded={async () => {
            setShowAdd(false);
            await reload();
          }}
        />
      )}
    </div>
  );
}

function AddMembershipForm({
  teamId,
  orgs,
  onClose,
  onAdded,
}: {
  teamId: string;
  orgs: Organization[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const [orgId, setOrgId] = useState("");
  const [seasonId, setSeasonId] = useState("");
  const [conferenceId, setConferenceId] = useState("");
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [confs, setConfs] = useState<Conference[]>([]);
  const [active, setActive] = useState(true);
  const [err, setErr] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!orgId) {
      setSeasons([]);
      setConfs([]);
      return;
    }
    Promise.all([
      adminFetch<Season[]>(`/api/admin/seasons?orgId=${orgId}&limit=50`),
      adminFetch<Conference[]>(`/api/admin/conferences?orgId=${orgId}&limit=100`),
    ]).then(([s, c]) => {
      setSeasons(s);
      setConfs(c);
      // pick active season by default
      const activeS = s.find((x) => x.active);
      setSeasonId(activeS?._id || "");
      setConferenceId("");
    });
  }, [orgId]);

  // Group conferences by tier for display
  const confsByTier = new Map<string, Conference[]>();
  for (const c of confs) {
    const key = c.tier || "";
    if (!confsByTier.has(key)) confsByTier.set(key, []);
    confsByTier.get(key)!.push(c);
  }

  async function submit() {
    setErr("");
    if (!orgId || !seasonId || !conferenceId) {
      setErr("Pick org, season, and conference.");
      return;
    }
    setSubmitting(true);
    try {
      await adminFetch(`/api/admin/memberships`, {
        method: "POST",
        body: JSON.stringify({ teamId, seasonId, conferenceId, active }),
      });
      onAdded();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-3 p-3 rounded border border-white/15 bg-black/30 space-y-2">
      <div className="grid sm:grid-cols-3 gap-2">
        <select
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          className="px-2 py-1.5 text-sm rounded bg-black/40 border border-white/20"
        >
          <option value="">Organization…</option>
          {orgs.map((o) => (
            <option key={o._id} value={o._id}>
              {o.abbreviation}
            </option>
          ))}
        </select>
        <select
          value={seasonId}
          onChange={(e) => setSeasonId(e.target.value)}
          disabled={!orgId}
          className="px-2 py-1.5 text-sm rounded bg-black/40 border border-white/20 disabled:opacity-40"
        >
          <option value="">Season…</option>
          {seasons.map((s) => (
            <option key={s._id} value={s._id}>
              {s.label}
              {s.active ? " · active" : ""}
            </option>
          ))}
        </select>
        <select
          value={conferenceId}
          onChange={(e) => setConferenceId(e.target.value)}
          disabled={!orgId}
          className="px-2 py-1.5 text-sm rounded bg-black/40 border border-white/20 disabled:opacity-40"
        >
          <option value="">Conference / Division…</option>
          {Array.from(confsByTier.entries()).map(([tier, list]) =>
            tier ? (
              <optgroup key={tier} label={tier}>
                {list.map((c) => (
                  <option key={c._id} value={c._id}>
                    {c.name}
                  </option>
                ))}
              </optgroup>
            ) : (
              list.map((c) => (
                <option key={c._id} value={c._id}>
                  {c.name}
                </option>
              ))
            ),
          )}
        </select>
      </div>
      <label className="flex items-center gap-2 text-xs text-white/60">
        <input
          type="checkbox"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
        />
        Active this semester
      </label>
      {err && <p className="text-xs text-red-400">{err}</p>}
      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          className="text-xs px-3 py-1 rounded border border-white/20 hover:bg-white/5"
        >
          Cancel
        </button>
        <button
          onClick={submit}
          disabled={submitting}
          className="text-xs px-3 py-1 rounded bg-white text-black font-semibold hover:bg-white/90 disabled:opacity-40"
        >
          {submitting ? "Adding…" : "Add"}
        </button>
      </div>
    </div>
  );
}
