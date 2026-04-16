"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Typeahead from "../Typeahead";
import {
  adminFetch,
  getToken,
  type League,
  type Player,
  type School,
  type Team,
} from "../adminClient";

type Game = "Valorant" | "League of Legends";
type Format = "BO1" | "BO3" | "BO5";

type ValPlayerRow = {
  playerId: string;
  playerLabel: string;
  playerQuery: string;
  agent: string;
  kills: number;
  deaths: number;
  assists: number;
  acs: number;
  firstKills: number;
  plants: number;
  defuses: number;
};

type ValMapState = {
  mapName: string;
  team1Score: number;
  team2Score: number;
  team1Players: ValPlayerRow[];
  team2Players: ValPlayerRow[];
};

type LolPlayerRow = {
  playerId: string;
  playerLabel: string;
  playerQuery: string;
  champion: string;
  role: string;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  gold: number;
  damage: number;
  vision: number;
  wards: number;
};

const BLANK_VAL_PLAYER = (): ValPlayerRow => ({
  playerId: "",
  playerLabel: "",
  playerQuery: "",
  agent: "",
  kills: 0,
  deaths: 0,
  assists: 0,
  acs: 0,
  firstKills: 0,
  plants: 0,
  defuses: 0,
});

const BLANK_LOL_PLAYER = (): LolPlayerRow => ({
  playerId: "",
  playerLabel: "",
  playerQuery: "",
  champion: "",
  role: "",
  kills: 0,
  deaths: 0,
  assists: 0,
  cs: 0,
  gold: 0,
  damage: 0,
  vision: 0,
  wards: 0,
});

const blankValMap = (): ValMapState => ({
  mapName: "",
  team1Score: 0,
  team2Score: 0,
  team1Players: Array.from({ length: 5 }, BLANK_VAL_PLAYER),
  team2Players: Array.from({ length: 5 }, BLANK_VAL_PLAYER),
});

export default function MatchEntryPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  const [game, setGame] = useState<Game>("Valorant");
  const [format, setFormat] = useState<Format>("BO1");
  const [date, setDate] = useState("");
  const [leagueQ, setLeagueQ] = useState("");
  const [league, setLeague] = useState<League | null>(null);

  // Team selection
  const [school1Q, setSchool1Q] = useState("");
  const [school1, setSchool1] = useState<School | null>(null);
  const [team1Q, setTeam1Q] = useState("");
  const [team1, setTeam1] = useState<Team | null>(null);

  const [school2Q, setSchool2Q] = useState("");
  const [school2, setSchool2] = useState<School | null>(null);
  const [team2Q, setTeam2Q] = useState("");
  const [team2, setTeam2] = useState<Team | null>(null);

  // Valorant
  const [maps, setMaps] = useState<ValMapState[]>([blankValMap()]);

  // LoL
  const [lolT1Score, setLolT1Score] = useState(0);
  const [lolT2Score, setLolT2Score] = useState(0);
  const [lolT1Players, setLolT1Players] = useState<LolPlayerRow[]>(
    Array.from({ length: 5 }, BLANK_LOL_PLAYER),
  );
  const [lolT2Players, setLolT2Players] = useState<LolPlayerRow[]>(
    Array.from({ length: 5 }, BLANK_LOL_PLAYER),
  );

  // Auto-populate players when a team is selected.
  // Keeps a roster cache so we can offer a swap picker.
  const [roster1, setRoster1] = useState<Player[]>([]);
  const [roster2, setRoster2] = useState<Player[]>([]);

  useEffect(() => {
    if (!team1?._id) { setRoster1([]); return; }
    fetchAllPlayersForTeam(team1._id).then((players) => {
      setRoster1(players);
      prefillPlayers(players, "team1");
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [team1?._id]);

  useEffect(() => {
    if (!team2?._id) { setRoster2([]); return; }
    fetchAllPlayersForTeam(team2._id).then((players) => {
      setRoster2(players);
      prefillPlayers(players, "team2");
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [team2?._id]);

  function prefillPlayers(players: Player[], side: "team1" | "team2") {
    const first5 = players.slice(0, 5);
    if (game === "Valorant") {
      setMaps((prev) =>
        prev.map((m) => {
          const key = side === "team1" ? "team1Players" : "team2Players";
          const filled = Array.from({ length: 5 }, (_, i) => {
            const p = first5[i];
            if (!p) return BLANK_VAL_PLAYER();
            return { ...BLANK_VAL_PLAYER(), playerId: p._id, playerLabel: p.displayName, playerQuery: p.displayName };
          });
          return { ...m, [key]: filled };
        }),
      );
    } else {
      const filled = Array.from({ length: 5 }, (_, i) => {
        const p = first5[i];
        if (!p) return BLANK_LOL_PLAYER();
        return { ...BLANK_LOL_PLAYER(), playerId: p._id, playerLabel: p.displayName, playerQuery: p.displayName };
      });
      if (side === "team1") setLolT1Players(filled);
      else setLolT2Players(filled);
    }
  }

  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router]);

  // Clear league when game changes
  useEffect(() => {
    setLeague(null);
    setLeagueQ("");
  }, [game]);

  const fetchLeagues = useCallback(
    async (q: string) =>
      adminFetch<League[]>(
        `/api/admin/leagues?game=${encodeURIComponent(game)}&q=${encodeURIComponent(q)}&limit=10`,
      ),
    [game],
  );

  const createLeague = useCallback(
    async (name: string) => {
      // Derive abbreviation from the name (first letters of each word, up to 6 chars)
      const abbreviation = name
        .split(/\s+/)
        .map((w) => w[0]?.toUpperCase() ?? "")
        .join("")
        .slice(0, 6) || name.slice(0, 6).toUpperCase();
      return adminFetch<League>(`/api/admin/leagues`, {
        method: "POST",
        body: JSON.stringify({ name, abbreviation, game }),
      });
    },
    [game],
  );

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

  const fetchTeamsForSchool = useCallback(
    (schoolId: string) => async (q: string) =>
      adminFetch<Team[]>(
        `/api/admin/teams?schoolId=${schoolId}&game=${encodeURIComponent(game)}&q=${encodeURIComponent(q)}&limit=15`,
      ),
    [game],
  );

  const createTeam = useCallback(
    (schoolId: string) => async (name: string) =>
      adminFetch<Team>(`/api/admin/teams`, {
        method: "POST",
        body: JSON.stringify({ schoolId, name, game }),
      }),
    [game],
  );

  const fetchPlayersRaw = useCallback(
    (teamId: string | undefined, q: string) =>
      adminFetch<Player[]>(
        `/api/admin/players?${teamId ? `teamId=${teamId}&` : ""}q=${encodeURIComponent(q)}&limit=15`,
      ),
    [],
  );

  const fetchAllPlayersForTeam = useCallback(
    (teamId: string) =>
      adminFetch<Player[]>(
        `/api/admin/players?teamId=${teamId}&limit=20`,
      ),
    [],
  );

  async function submit() {
    setMessage("");
    if (!team1 || !team2) {
      setMessage("Select both teams.");
      return;
    }
    if (team1._id === team2._id) {
      setMessage("Teams must differ.");
      return;
    }
    setSubmitting(true);
    try {
      const body: Record<string, unknown> = {
        game,
        team1Id: team1._id,
        team2Id: team2._id,
        format,
        date: date || undefined,
        leagueId: league?._id || undefined,
      };
      if (game === "Valorant") {
        body.maps = maps.map((m) => ({
          mapName: m.mapName,
          team1Score: m.team1Score,
          team2Score: m.team2Score,
          team1Players: m.team1Players
            .filter((p) => p.playerId)
            .map(stripValRow),
          team2Players: m.team2Players
            .filter((p) => p.playerId)
            .map(stripValRow),
        }));
      } else {
        body.team1Score = lolT1Score;
        body.team2Score = lolT2Score;
        body.lolTeam1Players = lolT1Players
          .filter((p) => p.playerId)
          .map(stripLolRow);
        body.lolTeam2Players = lolT2Players
          .filter((p) => p.playerId)
          .map(stripLolRow);
      }
      const res = await adminFetch<{ matchId: string }>(`/api/admin/matches`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage(`Match saved: ${res.matchId}`);
      setMaps([blankValMap()]);
      setLolT1Score(0);
      setLolT2Score(0);
      setLolT1Players(Array.from({ length: 5 }, BLANK_LOL_PLAYER));
      setLolT2Players(Array.from({ length: 5 }, BLANK_LOL_PLAYER));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-6xl mx-auto">
        <Link href="/admin" className="text-sm text-white/60 hover:text-white">
          ← Back
        </Link>
        <h1 className="text-2xl font-bold mt-2 mb-6">Enter Match</h1>

        <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <div>
            <label className="block text-xs text-white/50 mb-1">Game</label>
            <select
              value={game}
              onChange={(e) => setGame(e.target.value as Game)}
              className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
            >
              <option>Valorant</option>
              <option>League of Legends</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-white/50 mb-1">
              League (optional)
            </label>
            <Typeahead<League>
              placeholder="e.g. CVAL, NECC…"
              value={leagueQ}
              onChange={setLeagueQ}
              fetcher={fetchLeagues}
              render={(l) => `${l.abbreviation} — ${l.name}`}
              onSelect={(l) => {
                setLeague(l);
                setLeagueQ(l.abbreviation);
              }}
              onCreate={createLeague}
              createLabel={(q) => `+ Create league "${q}"`}
            />
            {league && (
              <p className="text-xs text-emerald-400 mt-1">{league.name}</p>
            )}
          </div>
          <div>
            <label className="block text-xs text-white/50 mb-1">Format</label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as Format)}
              className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
            >
              <option>BO1</option>
              <option>BO3</option>
              <option>BO5</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-white/50 mb-1">
              Date (optional)
            </label>
            <input
              type="datetime-local"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
            />
          </div>
        </section>

        <section className="grid md:grid-cols-2 gap-6 mb-8">
          <TeamPicker
            label="Team 1"
            schoolQ={school1Q}
            setSchoolQ={setSchool1Q}
            school={school1}
            setSchool={(s) => {
              setSchool1(s);
              setSchool1Q(s?.name ?? "");
              setTeam1(null);
              setTeam1Q("");
            }}
            teamQ={team1Q}
            setTeamQ={setTeam1Q}
            team={team1}
            setTeam={(t) => {
              setTeam1(t);
              setTeam1Q(t?.teamName ?? "");
            }}
            fetchSchools={fetchSchools}
            createSchool={createSchool}
            fetchTeamsForSchool={fetchTeamsForSchool}
            createTeam={createTeam}
          />
          <TeamPicker
            label="Team 2"
            schoolQ={school2Q}
            setSchoolQ={setSchool2Q}
            school={school2}
            setSchool={(s) => {
              setSchool2(s);
              setSchool2Q(s?.name ?? "");
              setTeam2(null);
              setTeam2Q("");
            }}
            teamQ={team2Q}
            setTeamQ={setTeam2Q}
            team={team2}
            setTeam={(t) => {
              setTeam2(t);
              setTeam2Q(t?.teamName ?? "");
            }}
            fetchSchools={fetchSchools}
            createSchool={createSchool}
            fetchTeamsForSchool={fetchTeamsForSchool}
            createTeam={createTeam}
          />
        </section>

        {game === "Valorant" ? (
          <ValorantMaps
            maps={maps}
            setMaps={setMaps}
            team1={team1}
            team2={team2}
            fetchPlayersRaw={fetchPlayersRaw}
            roster1={roster1}
            roster2={roster2}
          />
        ) : (
          <LolSeries
            t1Score={lolT1Score}
            t2Score={lolT2Score}
            setT1Score={setLolT1Score}
            setT2Score={setLolT2Score}
            t1Players={lolT1Players}
            t2Players={lolT2Players}
            setT1Players={setLolT1Players}
            setT2Players={setLolT2Players}
            team1={team1}
            team2={team2}
            fetchPlayersRaw={fetchPlayersRaw}
            roster1={roster1}
            roster2={roster2}
          />
        )}

        <div className="mt-8 flex items-center gap-4">
          <button
            onClick={submit}
            disabled={submitting}
            className="px-5 py-2 rounded bg-white text-black font-semibold disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save Match"}
          </button>
          {message && <span className="text-sm text-white/70">{message}</span>}
        </div>
      </div>
    </main>
  );
}

function stripValRow(r: ValPlayerRow) {
  return {
    playerId: r.playerId,
    agent: r.agent,
    kills: Number(r.kills),
    deaths: Number(r.deaths),
    assists: Number(r.assists),
    acs: Number(r.acs),
    firstKills: Number(r.firstKills),
    plants: Number(r.plants),
    defuses: Number(r.defuses),
  };
}

function stripLolRow(r: LolPlayerRow) {
  return {
    playerId: r.playerId,
    champion: r.champion,
    role: r.role,
    kills: Number(r.kills),
    deaths: Number(r.deaths),
    assists: Number(r.assists),
    cs: Number(r.cs),
    gold: Number(r.gold),
    damage: Number(r.damage),
    vision: Number(r.vision),
    wards: Number(r.wards),
  };
}

type TeamPickerProps = {
  label: string;
  schoolQ: string;
  setSchoolQ: (s: string) => void;
  school: School | null;
  setSchool: (s: School | null) => void;
  teamQ: string;
  setTeamQ: (s: string) => void;
  team: Team | null;
  setTeam: (t: Team | null) => void;
  fetchSchools: (q: string) => Promise<School[]>;
  createSchool: (name: string) => Promise<School>;
  fetchTeamsForSchool: (
    schoolId: string,
  ) => (q: string) => Promise<Team[]>;
  createTeam: (schoolId: string) => (name: string) => Promise<Team>;
};

function TeamPicker(p: TeamPickerProps) {
  return (
    <div className="p-5 rounded-xl border border-white/10 bg-white/5 space-y-3">
      <div className="font-semibold">{p.label}</div>
      <div>
        <label className="block text-xs text-white/50 mb-1">School</label>
        <Typeahead<School>
          placeholder="Type school name…"
          value={p.schoolQ}
          onChange={p.setSchoolQ}
          fetcher={p.fetchSchools}
          render={(s) => s.name}
          onSelect={p.setSchool}
          onCreate={p.createSchool}
          createLabel={(q) => `+ Create school "${q}"`}
        />
      </div>
      {p.school && (
        <div>
          <label className="block text-xs text-white/50 mb-1">
            Team at {p.school.name}
          </label>
          <Typeahead<Team>
            placeholder="e.g. CSU Vikes Green"
            value={p.teamQ}
            onChange={p.setTeamQ}
            fetcher={p.fetchTeamsForSchool(p.school._id)}
            render={(t) =>
              `${t.teamName}${t.tier ? ` (${t.tier})` : ""}`
            }
            onSelect={p.setTeam}
            onCreate={p.createTeam(p.school._id)}
            createLabel={(q) => `+ Create team "${q}"`}
          />
        </div>
      )}
      {p.team && (
        <div className="text-xs text-emerald-400">
          Selected: {p.team.teamName} · W{p.team.wins ?? 0}–L{p.team.losses ?? 0}
        </div>
      )}
    </div>
  );
}

// ---------- Valorant maps ----------

function ValorantMaps({
  maps,
  setMaps,
  team1,
  team2,
  fetchPlayersRaw,
  roster1,
  roster2,
}: {
  maps: ValMapState[];
  setMaps: (m: ValMapState[]) => void;
  team1: Team | null;
  team2: Team | null;
  fetchPlayersRaw: (teamId: string | undefined, q: string) => Promise<Player[]>;
  roster1: Player[];
  roster2: Player[];
}) {
  const fetcher1 = useMemo(
    () => (q: string) => fetchPlayersRaw(team1?._id, q),
    [fetchPlayersRaw, team1?._id],
  );
  const fetcher2 = useMemo(
    () => (q: string) => fetchPlayersRaw(team2?._id, q),
    [fetchPlayersRaw, team2?._id],
  );

  function update(i: number, next: Partial<ValMapState>) {
    setMaps(maps.map((m, idx) => (idx === i ? { ...m, ...next } : m)));
  }

  return (
    <section className="space-y-6">
      {maps.map((m, i) => (
        <div
          key={i}
          className="p-5 rounded-xl border border-white/10 bg-white/5 space-y-4"
        >
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="font-semibold">Map {i + 1}</h3>
            <input
              placeholder="Map name (e.g. Ascent)"
              value={m.mapName}
              onChange={(e) => update(i, { mapName: e.target.value })}
              className="px-3 py-1.5 rounded bg-black/40 border border-white/20"
            />
            <label className="text-xs text-white/60">
              {team1?.teamName || "T1"} score
            </label>
            <input
              type="number"
              min={0}
              value={m.team1Score}
              onChange={(e) =>
                update(i, { team1Score: Number(e.target.value) })
              }
              className="w-16 px-2 py-1 rounded bg-black/40 border border-white/20"
            />
            <label className="text-xs text-white/60">
              {team2?.teamName || "T2"} score
            </label>
            <input
              type="number"
              min={0}
              value={m.team2Score}
              onChange={(e) =>
                update(i, { team2Score: Number(e.target.value) })
              }
              className="w-16 px-2 py-1 rounded bg-black/40 border border-white/20"
            />
            {maps.length > 1 && (
              <button
                type="button"
                onClick={() => setMaps(maps.filter((_, idx) => idx !== i))}
                className="ml-auto text-red-400 text-sm"
              >
                Remove map
              </button>
            )}
          </div>
          <ValPlayerTable
            label={team1?.teamName ?? "Team 1"}
            players={m.team1Players}
            setPlayers={(pl) => update(i, { team1Players: pl })}
            fetchPlayers={fetcher1}
            roster={roster1}
          />
          <ValPlayerTable
            label={team2?.teamName ?? "Team 2"}
            players={m.team2Players}
            setPlayers={(pl) => update(i, { team2Players: pl })}
            fetchPlayers={fetcher2}
            roster={roster2}
          />
        </div>
      ))}
      <button
        type="button"
        onClick={() => setMaps([...maps, blankValMap()])}
        className="px-4 py-2 rounded border border-white/20 text-sm hover:bg-white/10"
      >
        + Add Map
      </button>
    </section>
  );
}

function ValPlayerTable({
  label,
  players,
  setPlayers,
  fetchPlayers,
  roster,
}: {
  label: string;
  players: ValPlayerRow[];
  setPlayers: (p: ValPlayerRow[]) => void;
  fetchPlayers: (q: string) => Promise<Player[]>;
  roster: Player[];
}) {
  function update(i: number, next: Partial<ValPlayerRow>) {
    setPlayers(players.map((p, idx) => (idx === i ? { ...p, ...next } : p)));
  }

  function swapPlayer(i: number, pl: Player) {
    update(i, {
      playerId: pl._id,
      playerLabel: pl.displayName,
      playerQuery: pl.displayName,
    });
  }

  const selectedIds = new Set(players.map((p) => p.playerId).filter(Boolean));
  const bench = roster.filter((p) => !selectedIds.has(p._id));

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <span className="text-sm font-medium">{label}</span>
        {bench.length > 0 && (
          <span className="text-xs text-white/40">
            Bench: {bench.map((b) => b.displayName).join(", ")}
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-white/50">
            <tr>
              <th className="text-left py-1">Player</th>
              <th className="text-left">Agent</th>
              <th>ACS</th>
              <th>K</th>
              <th>D</th>
              <th>A</th>
              <th>FK</th>
              <th>Plants</th>
              <th>Defuses</th>
              {bench.length > 0 && <th></th>}
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => (
              <tr key={i} className="border-t border-white/10">
                <td className="py-1 pr-2 min-w-[200px]">
                  <Typeahead<Player>
                    placeholder="Player…"
                    value={p.playerQuery}
                    onChange={(v) => update(i, { playerQuery: v })}
                    fetcher={fetchPlayers}
                    render={(pl) => `${pl.displayName} (${pl.riotId ?? "—"})`}
                    onSelect={(pl) =>
                      update(i, {
                        playerId: pl._id,
                        playerLabel: pl.displayName,
                        playerQuery: pl.displayName,
                      })
                    }
                  />
                </td>
                <td className="pr-2">
                  <input
                    value={p.agent}
                    onChange={(e) => update(i, { agent: e.target.value })}
                    className="w-24 px-2 py-1 rounded bg-black/40 border border-white/20"
                  />
                </td>
                {(["acs", "kills", "deaths", "assists", "firstKills", "plants", "defuses"] as const).map(
                  (k) => (
                    <td key={k} className="text-center">
                      <input
                        type="number"
                        value={p[k]}
                        onChange={(e) =>
                          update(i, { [k]: Number(e.target.value) } as Partial<ValPlayerRow>)
                        }
                        className="w-14 px-1 py-1 rounded bg-black/40 border border-white/20 text-center"
                      />
                    </td>
                  ),
                )}
                {bench.length > 0 && (
                  <td className="pl-1">
                    <select
                      value=""
                      onChange={(e) => {
                        const sub = bench.find((b) => b._id === e.target.value);
                        if (sub) swapPlayer(i, sub);
                      }}
                      className="w-20 text-xs px-1 py-1 rounded bg-black/40 border border-white/20 text-white/60"
                    >
                      <option value="">Swap</option>
                      {bench.map((b) => (
                        <option key={b._id} value={b._id}>
                          {b.displayName}
                        </option>
                      ))}
                    </select>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------- LoL series ----------

function LolSeries({
  t1Score,
  t2Score,
  setT1Score,
  setT2Score,
  t1Players,
  t2Players,
  setT1Players,
  setT2Players,
  team1,
  team2,
  fetchPlayersRaw,
  roster1,
  roster2,
}: {
  t1Score: number;
  t2Score: number;
  setT1Score: (n: number) => void;
  setT2Score: (n: number) => void;
  t1Players: LolPlayerRow[];
  t2Players: LolPlayerRow[];
  setT1Players: (p: LolPlayerRow[]) => void;
  setT2Players: (p: LolPlayerRow[]) => void;
  team1: Team | null;
  team2: Team | null;
  fetchPlayersRaw: (teamId: string | undefined, q: string) => Promise<Player[]>;
  roster1: Player[];
  roster2: Player[];
}) {
  const fetcher1 = useMemo(
    () => (q: string) => fetchPlayersRaw(team1?._id, q),
    [fetchPlayersRaw, team1?._id],
  );
  const fetcher2 = useMemo(
    () => (q: string) => fetchPlayersRaw(team2?._id, q),
    [fetchPlayersRaw, team2?._id],
  );

  return (
    <section className="space-y-6">
      <div className="p-5 rounded-xl border border-white/10 bg-white/5 space-y-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h3 className="font-semibold">Series Score</h3>
          <label className="text-xs text-white/60">
            {team1?.teamName || "T1"}
          </label>
          <input
            type="number"
            min={0}
            value={t1Score}
            onChange={(e) => setT1Score(Number(e.target.value))}
            className="w-16 px-2 py-1 rounded bg-black/40 border border-white/20"
          />
          <label className="text-xs text-white/60">
            {team2?.teamName || "T2"}
          </label>
          <input
            type="number"
            min={0}
            value={t2Score}
            onChange={(e) => setT2Score(Number(e.target.value))}
            className="w-16 px-2 py-1 rounded bg-black/40 border border-white/20"
          />
        </div>
        <LolPlayerTable
          label={team1?.teamName ?? "Team 1"}
          players={t1Players}
          setPlayers={setT1Players}
          fetchPlayers={fetcher1}
          roster={roster1}
        />
        <LolPlayerTable
          label={team2?.teamName ?? "Team 2"}
          players={t2Players}
          setPlayers={setT2Players}
          fetchPlayers={fetcher2}
          roster={roster2}
        />
      </div>
    </section>
  );
}

function LolPlayerTable({
  label,
  players,
  setPlayers,
  fetchPlayers,
  roster,
}: {
  label: string;
  players: LolPlayerRow[];
  setPlayers: (p: LolPlayerRow[]) => void;
  fetchPlayers: (q: string) => Promise<Player[]>;
  roster: Player[];
}) {
  function update(i: number, next: Partial<LolPlayerRow>) {
    setPlayers(players.map((p, idx) => (idx === i ? { ...p, ...next } : p)));
  }

  function swapPlayer(i: number, pl: Player) {
    update(i, {
      playerId: pl._id,
      playerLabel: pl.displayName,
      playerQuery: pl.displayName,
    });
  }

  const selectedIds = new Set(players.map((p) => p.playerId).filter(Boolean));
  const bench = roster.filter((p) => !selectedIds.has(p._id));

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <span className="text-sm font-medium">{label}</span>
        {bench.length > 0 && (
          <span className="text-xs text-white/40">
            Bench: {bench.map((b) => b.displayName).join(", ")}
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-white/50">
            <tr>
              <th className="text-left py-1">Player</th>
              <th className="text-left">Champion</th>
              <th className="text-left">Role</th>
              <th>K</th>
              <th>D</th>
              <th>A</th>
              <th>CS</th>
              <th>Gold</th>
              <th>Dmg</th>
              <th>Vision</th>
              <th>Wards</th>
              {bench.length > 0 && <th></th>}
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => (
              <tr key={i} className="border-t border-white/10">
                <td className="py-1 pr-2 min-w-[200px]">
                  <Typeahead<Player>
                    placeholder="Player…"
                    value={p.playerQuery}
                    onChange={(v) => update(i, { playerQuery: v })}
                    fetcher={fetchPlayers}
                    render={(pl) => `${pl.displayName} (${pl.riotId ?? "—"})`}
                    onSelect={(pl) =>
                      update(i, {
                        playerId: pl._id,
                        playerLabel: pl.displayName,
                        playerQuery: pl.displayName,
                      })
                    }
                  />
                </td>
                <td className="pr-2">
                  <input
                    value={p.champion}
                    onChange={(e) => update(i, { champion: e.target.value })}
                    className="w-28 px-2 py-1 rounded bg-black/40 border border-white/20"
                  />
                </td>
                <td className="pr-2">
                  <input
                    value={p.role}
                    onChange={(e) => update(i, { role: e.target.value })}
                    className="w-20 px-2 py-1 rounded bg-black/40 border border-white/20"
                  />
                </td>
                {(["kills", "deaths", "assists", "cs", "gold", "damage", "vision", "wards"] as const).map(
                  (k) => (
                    <td key={k} className="text-center">
                      <input
                        type="number"
                        value={p[k]}
                        onChange={(e) =>
                          update(i, { [k]: Number(e.target.value) } as Partial<LolPlayerRow>)
                        }
                        className="w-16 px-1 py-1 rounded bg-black/40 border border-white/20 text-center"
                      />
                    </td>
                  ),
                )}
                {bench.length > 0 && (
                  <td className="pl-1">
                    <select
                      value=""
                      onChange={(e) => {
                        const sub = bench.find((b) => b._id === e.target.value);
                        if (sub) swapPlayer(i, sub);
                      }}
                      className="w-20 text-xs px-1 py-1 rounded bg-black/40 border border-white/20 text-white/60"
                    >
                      <option value="">Swap</option>
                      {bench.map((b) => (
                        <option key={b._id} value={b._id}>
                          {b.displayName}
                        </option>
                      ))}
                    </select>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
