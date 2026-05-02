"use client";

import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

type ValPlayer = {
  playerId: string;
  playerName?: string;
  agent: string;
  kills: number;
  deaths: number;
  assists: number;
  acs: number;
  firstKills?: number;
  plants?: number;
  defuses?: number;
};

type ValMap = {
  mapName: string;
  team1Score: number;
  team2Score: number;
  team1Players: ValPlayer[];
  team2Players: ValPlayer[];
};

type LolPlayer = {
  playerId: string;
  playerName?: string;
  champion: string;
  role: string;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  gold: number;
  damage: number;
  vision?: number;
  wards?: number;
};

type Match = {
  _id: string;
  game: string;
  team1Name?: string;
  team2Name?: string;
  team1Score?: number;
  team2Score?: number;
  winnerTeamId?: string;
  team1Id?: string;
  format?: string;
  date?: string;
  leagueName?: string;
  orgAbbreviation?: string;
  seasonLabel?: string;
  conferenceName?: string;
  maps?: ValMap[];
  players?: { team1: LolPlayer[]; team2: LolPlayer[] };
};

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

function formatDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function kda(k: number, d: number, a: number): string {
  if (d === 0) return "Perfect";
  return ((k + a) / d).toFixed(2);
}

function ValPlayerTable({ players, teamName, teamColor }: { players: ValPlayer[]; teamName: string; teamColor: string }) {
  return (
    <div style={s.playerSection}>
      <div style={{ ...s.teamLabel, color: teamColor }}>{teamName}</div>
      <div style={{ overflowX: "auto" }}>
        <table style={s.table}>
          <thead>
            <tr style={s.tableHead}>
              <th style={{ ...s.th, textAlign: "left", minWidth: 120 }}>Player</th>
              <th style={{ ...s.th, minWidth: 80 }}>Agent</th>
              <th style={s.th}>ACS</th>
              <th style={s.th}>K</th>
              <th style={s.th}>D</th>
              <th style={s.th}>A</th>
              <th style={s.th}>KDA</th>
              <th style={s.th}>FK</th>
              <th style={s.th}>Plants</th>
              <th style={s.th}>Defuses</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => (
              <tr key={i} style={s.tableRow}>
                <td style={{ ...s.td, fontWeight: 600, textAlign: "left" }}>
                  {p.playerName || p.playerId}
                </td>
                <td style={{ ...s.td, color: "#a78bfa" }}>{p.agent}</td>
                <td style={{ ...s.td, fontWeight: 700, color: "#fbbf24" }} className="tabular-nums">{p.acs}</td>
                <td style={{ ...s.td, color: "#22c55e" }} className="tabular-nums">{p.kills}</td>
                <td style={{ ...s.td, color: "#f87171" }} className="tabular-nums">{p.deaths}</td>
                <td style={{ ...s.td, color: "#60a5fa" }} className="tabular-nums">{p.assists}</td>
                <td style={s.td} className="tabular-nums">{kda(p.kills, p.deaths, p.assists)}</td>
                <td style={{ ...s.td, opacity: 0.7 }} className="tabular-nums">{p.firstKills ?? 0}</td>
                <td style={{ ...s.td, opacity: 0.7 }} className="tabular-nums">{p.plants ?? 0}</td>
                <td style={{ ...s.td, opacity: 0.7 }} className="tabular-nums">{p.defuses ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LolPlayerTable({ players, teamName, teamColor }: { players: LolPlayer[]; teamName: string; teamColor: string }) {
  return (
    <div style={s.playerSection}>
      <div style={{ ...s.teamLabel, color: teamColor }}>{teamName}</div>
      <div style={{ overflowX: "auto" }}>
        <table style={s.table}>
          <thead>
            <tr style={s.tableHead}>
              <th style={{ ...s.th, textAlign: "left", minWidth: 120 }}>Player</th>
              <th style={{ ...s.th, minWidth: 90 }}>Champion</th>
              <th style={{ ...s.th, minWidth: 80 }}>Role</th>
              <th style={s.th}>K</th>
              <th style={s.th}>D</th>
              <th style={s.th}>A</th>
              <th style={s.th}>KDA</th>
              <th style={s.th}>CS</th>
              <th style={s.th}>Gold</th>
              <th style={s.th}>Dmg</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => (
              <tr key={i} style={s.tableRow}>
                <td style={{ ...s.td, fontWeight: 600, textAlign: "left" }}>{p.playerName || p.playerId}</td>
                <td style={{ ...s.td, color: "#a78bfa" }}>{p.champion}</td>
                <td style={{ ...s.td, opacity: 0.7, fontSize: "0.8rem" }}>{p.role}</td>
                <td style={{ ...s.td, color: "#22c55e" }} className="tabular-nums">{p.kills}</td>
                <td style={{ ...s.td, color: "#f87171" }} className="tabular-nums">{p.deaths}</td>
                <td style={{ ...s.td, color: "#60a5fa" }} className="tabular-nums">{p.assists}</td>
                <td style={s.td} className="tabular-nums">{kda(p.kills, p.deaths, p.assists)}</td>
                <td style={{ ...s.td, opacity: 0.7 }} className="tabular-nums">{p.cs}</td>
                <td style={{ ...s.td, opacity: 0.7 }} className="tabular-nums">{(p.gold / 1000).toFixed(1)}k</td>
                <td style={{ ...s.td, opacity: 0.7 }} className="tabular-nums">{(p.damage / 1000).toFixed(1)}k</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MatchDetailContent() {
  const params = useParams();
  const id = params?.id as string;
  const [match, setMatch] = useState<Match | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/api/matches/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load match (${r.status})`);
        return r.json() as Promise<Match>;
      })
      .then((d) => { setMatch(d); setLoaded(true); })
      .catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) {
    return (
      <main style={s.container}>
        <div className="page-content">
          <Link href="/matches" style={s.backLink}>← Back to matches</Link>
          <p style={{ color: "#f87171", marginTop: "2rem" }}>{error}</p>
        </div>
      </main>
    );
  }

  if (!loaded) {
    return (
      <main style={s.container}>
        <div className="page-content">
          <Link href="/matches" style={s.backLink}>← Back to matches</Link>
          <div style={{ marginTop: "2rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton-line" style={{ height: 48, opacity: 1 - i * 0.15 }} />
            ))}
          </div>
        </div>
      </main>
    );
  }

  if (!match) return null;

  const isVal = match.game === "valorant";
  const gameColor = isVal ? "#ff4655" : "#c89b3c";
  const t1Won = match.winnerTeamId === match.team1Id;
  const leagueLabel = match.leagueName
    || [match.orgAbbreviation, match.seasonLabel, match.conferenceName].filter(Boolean).join(" — ")
    || "—";

  return (
    <main style={s.container}>
      <div className="page-content">
        <Link href="/matches" style={s.backLink}>← Back to matches</Link>

        {/* Header card */}
        <section style={{ ...s.headerCard, borderColor: `${gameColor}44` }}>
          <div style={s.metaRow}>
            <span style={{ ...s.gameBadge, background: isVal ? "rgba(255,70,85,0.15)" : "rgba(200,155,60,0.15)", color: gameColor }}>
              {isVal ? "Valorant" : "League of Legends"}
            </span>
            <span style={s.metaText}>{match.format ?? ""}</span>
            <span style={s.metaText}>{formatDate(match.date)}</span>
            <span style={{ ...s.metaText, opacity: 0.5 }}>{leagueLabel}</span>
          </div>

          <div style={s.scoreRow}>
            <div style={{ ...s.teamBlock, textAlign: "right" }}>
              <span style={{ ...s.teamName, color: t1Won ? "#22c55e" : "white", opacity: t1Won ? 1 : 0.65 }}>
                {match.team1Name}
              </span>
              {t1Won && <span style={s.winBadge}>W</span>}
            </div>
            <div style={s.scoreBlock}>
              <span style={{ ...s.scoreNum, color: t1Won ? "#22c55e" : "white" }}>{match.team1Score ?? 0}</span>
              <span style={s.scoreSep}>–</span>
              <span style={{ ...s.scoreNum, color: !t1Won ? "#22c55e" : "white" }}>{match.team2Score ?? 0}</span>
            </div>
            <div style={{ ...s.teamBlock, textAlign: "left" }}>
              {!t1Won && <span style={s.winBadge}>W</span>}
              <span style={{ ...s.teamName, color: !t1Won ? "#22c55e" : "white", opacity: !t1Won ? 1 : 0.65 }}>
                {match.team2Name}
              </span>
            </div>
          </div>
        </section>

        {/* Valorant: map-by-map */}
        {isVal && match.maps && match.maps.length > 0 && (
          <div style={s.mapsContainer}>
            {match.maps.map((mapData, mi) => {
              const m1Won = mapData.team1Score > mapData.team2Score;
              return (
                <section key={mi} style={s.mapCard}>
                  <div style={s.mapHeader}>
                    <span style={s.mapName}>{mapData.mapName}</span>
                    <div style={s.mapScore}>
                      <span style={{ color: m1Won ? "#22c55e" : "rgba(255,255,255,0.55)", fontWeight: 700 }}>
                        {mapData.team1Score}
                      </span>
                      <span style={{ opacity: 0.3, margin: "0 0.5rem" }}>–</span>
                      <span style={{ color: !m1Won ? "#22c55e" : "rgba(255,255,255,0.55)", fontWeight: 700 }}>
                        {mapData.team2Score}
                      </span>
                    </div>
                  </div>
                  <ValPlayerTable
                    players={mapData.team1Players}
                    teamName={match.team1Name ?? "Team 1"}
                    teamColor={t1Won ? "#22c55e" : "#60a5fa"}
                  />
                  <ValPlayerTable
                    players={mapData.team2Players}
                    teamName={match.team2Name ?? "Team 2"}
                    teamColor={!t1Won ? "#22c55e" : "#60a5fa"}
                  />
                </section>
              );
            })}
          </div>
        )}

        {/* LoL: single game stats */}
        {!isVal && match.players && (
          <section style={s.mapCard}>
            <LolPlayerTable
              players={match.players.team1}
              teamName={match.team1Name ?? "Team 1"}
              teamColor={t1Won ? "#22c55e" : "#60a5fa"}
            />
            <LolPlayerTable
              players={match.players.team2}
              teamName={match.team2Name ?? "Team 2"}
              teamColor={!t1Won ? "#22c55e" : "#60a5fa"}
            />
          </section>
        )}

        {isVal && (!match.maps || match.maps.length === 0) && (
          <p style={{ opacity: 0.45, marginTop: "2rem" }}>No map data recorded for this match.</p>
        )}
        {!isVal && (!match.players || (!match.players.team1?.length && !match.players.team2?.length)) && (
          <p style={{ opacity: 0.45, marginTop: "2rem" }}>No player data recorded for this match.</p>
        )}
      </div>
    </main>
  );
}

export default function MatchDetailPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" }} />}>
      <MatchDetailContent />
    </Suspense>
  );
}

const s: Record<string, CSSProperties> = {
  container: { minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" },
  backLink: { color: "rgba(255,255,255,0.5)", textDecoration: "none", fontSize: "0.9rem", display: "inline-block", marginBottom: "1.5rem" },

  headerCard: {
    border: "1px solid",
    background: "rgba(255,255,255,0.04)",
    borderRadius: 16,
    padding: "1.5rem",
    marginBottom: "1.5rem",
  },
  metaRow: { display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap", marginBottom: "1.25rem" },
  gameBadge: { padding: "0.2rem 0.7rem", borderRadius: 6, fontSize: "0.8rem", fontWeight: 700 },
  metaText: { fontSize: "0.85rem", opacity: 0.6 },

  scoreRow: {
    display: "grid",
    gridTemplateColumns: "1fr auto 1fr",
    alignItems: "center",
    gap: "1rem",
  },
  teamBlock: { display: "flex", alignItems: "center", gap: "0.5rem" },
  teamName: { fontSize: "clamp(1rem, 2.5vw, 1.5rem)", fontWeight: 700, letterSpacing: "-0.01em" },
  winBadge: {
    background: "rgba(34,197,94,0.2)",
    color: "#22c55e",
    fontSize: "0.7rem",
    fontWeight: 700,
    padding: "0.15rem 0.45rem",
    borderRadius: 5,
  },
  scoreBlock: { textAlign: "center" as const },
  scoreNum: { fontSize: "clamp(1.8rem, 5vw, 3rem)", fontWeight: 800 },
  scoreSep: { opacity: 0.2, fontSize: "2rem", margin: "0 0.4rem" },

  mapsContainer: { display: "flex", flexDirection: "column" as const, gap: "1.25rem" },
  mapCard: {
    border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.03)",
    borderRadius: 14,
    overflow: "hidden",
  },
  mapHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0.85rem 1.25rem",
    background: "rgba(255,255,255,0.05)",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
  },
  mapName: { fontWeight: 700, fontSize: "1rem", letterSpacing: "0.03em", textTransform: "uppercase" as const },
  mapScore: { display: "flex", alignItems: "center", fontSize: "1.1rem" },

  playerSection: { padding: "0.75rem 1.25rem 1rem" },
  teamLabel: { fontWeight: 700, fontSize: "0.85rem", marginBottom: "0.5rem", textTransform: "uppercase" as const, letterSpacing: "0.05em" },

  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: "0.875rem" },
  tableHead: { borderBottom: "1px solid rgba(255,255,255,0.08)" },
  tableRow: { borderBottom: "1px solid rgba(255,255,255,0.04)" },
  th: {
    padding: "0.4rem 0.75rem",
    textAlign: "center" as const,
    fontWeight: 700,
    fontSize: "0.75rem",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    opacity: 0.6,
    whiteSpace: "nowrap" as const,
  },
  td: { padding: "0.55rem 0.75rem", textAlign: "center" as const, whiteSpace: "nowrap" as const },
};
