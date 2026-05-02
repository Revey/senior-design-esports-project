"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { CSSProperties } from "react";
import { formatLabel } from "../../_shared/gameLabel";

type RosterEntry = {
  name?: string;
  role?: string | null;
  riotId?: string | null;
  slug?: string;
  active?: boolean;
};

type RecentMatch = {
  matchId: string;
  date?: string;
  game?: string;
  format?: string;
  opponent?: string;
  ownScore?: number | null;
  oppScore?: number | null;
  win?: boolean | null;
};

type TeamProfile = {
  slug: string;
  name: string;
  school: string;
  game: string;
  record: { wins: number; losses: number };
  winRate: number;
  rating: number;
  region: string;
  leagueSlug: string;
  roster: RosterEntry[];
  recentMatches: RecentMatch[];
  mapRecord: { wins: number; losses: number };
};

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

function ratingColor(r: number): string {
  if (r >= 1800) return "#22c55e";
  if (r >= 1600) return "#eab308";
  return "#f97316";
}

function formatDate(iso?: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function TeamProfilePage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug;
  const [team, setTeam] = useState<TeamProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setError(null);
    fetch(`${API}/api/teams/${slug}`)
      .then((r) => {
        if (r.status === 404) throw new Error("Team not found");
        if (!r.ok) throw new Error(`Failed to load team (${r.status})`);
        return r.json() as Promise<TeamProfile>;
      })
      .then(setTeam)
      .catch((e: Error) => setError(e.message));
  }, [slug]);

  if (error) {
    return (
      <main style={s.container}>
        <div className="page-content">
          <Link href="/teams" style={s.backLink}>← Back to teams</Link>
          <h1 style={s.title}>{error}</h1>
        </div>
      </main>
    );
  }

  if (!team) {
    return (
      <main style={s.container}>
        <div className="page-content">
          <Link href="/teams" style={s.backLink}>← Back to teams</Link>
          <div className="skeleton-line" style={{ height: 48, marginTop: 16, width: "40%" }} />
          <div className="skeleton-line" style={{ height: 24, marginTop: 12, width: "25%" }} />
          <div className="skeleton-line" style={{ height: 200, marginTop: 24 }} />
        </div>
      </main>
    );
  }

  const isVal = team.game === "valorant";
  const accent = isVal ? "#ff4655" : "#c89b3c";
  const hasMapRecord = team.mapRecord.wins > 0 || team.mapRecord.losses > 0;
  const totalMaps = team.mapRecord.wins + team.mapRecord.losses;
  const mapWinRate = totalMaps > 0 ? Math.round((team.mapRecord.wins / totalMaps) * 1000) / 10 : null;

  return (
    <main style={s.container}>
      <div className="page-content">
        <Link href="/teams" style={s.backLink}>← Back to teams</Link>

        {/* Header */}
        <header style={{ ...s.header, borderColor: `${accent}55` }}>
          <div>
            <div style={s.nameRow}>
              <h1 style={s.title}>{team.name}</h1>
              <span style={{ ...s.gameBadge, background: `${accent}22`, color: accent, borderColor: `${accent}88` }}>
                {isVal ? "VALORANT" : "LEAGUE OF LEGENDS"}
              </span>
            </div>
            <p style={s.subtitle}>
              <span style={{ opacity: 0.8 }}>{team.school}</span>
              <span style={{ opacity: 0.3, margin: "0 0.6rem" }}>·</span>
              <span style={{ opacity: 0.65 }}>{team.region}</span>
              {team.leagueSlug && (
                <>
                  <span style={{ opacity: 0.3, margin: "0 0.6rem" }}>·</span>
                  <Link href={`/leagues`} style={{ color: accent, textDecoration: "none", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", fontSize: "0.85rem" }}>
                    {team.leagueSlug}
                  </Link>
                </>
              )}
            </p>
          </div>
          <div style={s.ratingBlock}>
            <div style={{ fontSize: "0.75rem", opacity: 0.5, letterSpacing: "0.08em" }}>RATING</div>
            <div style={{ fontSize: "2.4rem", fontWeight: 800, color: ratingColor(team.rating) }} className="tabular-nums">
              {team.rating}
            </div>
          </div>
        </header>

        {/* Record cards */}
        <section style={s.statGrid}>
          <div style={s.statCell}>
            <div style={s.statLabel}>Series record</div>
            <div style={s.statValue} className="tabular-nums">
              {team.record.wins}<span style={{ opacity: 0.3 }}>-</span>{team.record.losses}
            </div>
          </div>
          <div style={s.statCell}>
            <div style={s.statLabel}>Win rate</div>
            <div style={s.statValue} className="tabular-nums">{team.winRate}%</div>
          </div>
          <div style={s.statCell}>
            <div style={s.statLabel}>Map record</div>
            <div style={s.statValue} className="tabular-nums">
              {hasMapRecord
                ? <>{team.mapRecord.wins}<span style={{ opacity: 0.3 }}>-</span>{team.mapRecord.losses}</>
                : <span style={{ opacity: 0.35, fontSize: "1rem" }}>—</span>}
            </div>
          </div>
          <div style={s.statCell}>
            <div style={s.statLabel}>Map win %</div>
            <div style={s.statValue} className="tabular-nums">
              {mapWinRate !== null ? `${mapWinRate}%` : <span style={{ opacity: 0.35, fontSize: "1rem" }}>—</span>}
            </div>
          </div>
        </section>

        {/* Roster */}
        <section style={s.card}>
          <h2 style={s.sectionTitle}>Roster</h2>
          {team.roster.length === 0 ? (
            <p style={s.emptyText}>No roster on file yet.</p>
          ) : (
            <div style={s.rosterGrid}>
              {team.roster.map((p, i) => {
                const inner = (
                  <div style={s.rosterCard}>
                    <div style={{ fontWeight: 600 }}>{p.name ?? "Unknown"}</div>
                    <div style={{ opacity: 0.55, fontSize: "0.85rem", marginTop: 2 }}>
                      {p.role ?? "—"}
                      {p.riotId && <span style={{ marginLeft: 8, opacity: 0.6 }}>· {p.riotId}</span>}
                    </div>
                    {p.active === false && (
                      <span style={{ ...s.inactiveBadge }}>Inactive</span>
                    )}
                  </div>
                );
                return p.slug ? (
                  <Link key={`${p.name}-${i}`} href={`/players/${p.slug}`} style={{ textDecoration: "none", color: "inherit" }}>
                    {inner}
                  </Link>
                ) : (
                  <div key={`${p.name}-${i}`}>{inner}</div>
                );
              })}
            </div>
          )}
        </section>

        {/* Recent matches */}
        <section style={s.card}>
          <h2 style={s.sectionTitle}>Recent matches</h2>
          {team.recentMatches.length === 0 ? (
            <p style={s.emptyText}>No logged matches yet.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={s.table}>
                <thead>
                  <tr style={s.tableHeadRow}>
                    <th style={s.th}>Result</th>
                    <th style={s.th}>Date</th>
                    <th style={s.th}>Opponent</th>
                    <th style={s.th}>Format</th>
                    <th style={s.thRight}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {team.recentMatches.map((m) => (
                    <tr key={m.matchId} style={s.tableRow}>
                      <td style={s.td}>
                        <span style={{ ...s.resultPill, background: m.win ? "#22c55e22" : "#ef444422", color: m.win ? "#22c55e" : "#ef4444" }}>
                          {m.win == null ? "-" : m.win ? "W" : "L"}
                        </span>
                      </td>
                      <td style={s.td}>{formatDate(m.date)}</td>
                      <td style={s.td}>{m.opponent ?? "-"}</td>
                      <td style={s.td}>{m.format ? formatLabel(m.format) : "-"}</td>
                      <td style={s.tdRight} className="tabular-nums">
                        {m.ownScore ?? "-"}<span style={{ opacity: 0.3 }}> - </span>{m.oppScore ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

const s: Record<string, CSSProperties> = {
  container: { minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" },
  backLink: { color: "rgba(255,255,255,0.55)", textDecoration: "none", fontSize: "0.85rem", display: "inline-block", marginBottom: "1.25rem" },

  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "1.5rem",
    padding: "1.5rem",
    borderRadius: 14,
    border: "1px solid",
    background: "rgba(255,255,255,0.02)",
    marginBottom: "1.5rem",
    flexWrap: "wrap",
  },
  nameRow: { display: "flex", alignItems: "center", gap: "0.8rem", flexWrap: "wrap" },
  title: { fontSize: "clamp(1.8rem, 3.5vw, 2.6rem)", fontWeight: 800, letterSpacing: "-0.02em", margin: 0 },
  subtitle: { marginTop: "0.5rem", fontSize: "0.95rem" },
  gameBadge: {
    fontSize: "0.7rem",
    fontWeight: 700,
    letterSpacing: "0.08em",
    padding: "0.3rem 0.7rem",
    borderRadius: 6,
    border: "1px solid",
  },
  ratingBlock: { textAlign: "right" },

  statGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "0.8rem", marginBottom: "1.25rem" },
  statCell: { padding: "1rem 1.1rem", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" },
  statLabel: { fontSize: "0.7rem", opacity: 0.5, letterSpacing: "0.08em", textTransform: "uppercase" },
  statValue: { fontSize: "1.7rem", fontWeight: 700, marginTop: "0.25rem" },

  card: {
    padding: "1.25rem 1.5rem",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.08)",
    background: "rgba(255,255,255,0.02)",
    marginBottom: "1.25rem",
  },
  sectionTitle: { fontSize: "0.8rem", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.55, margin: "0 0 1rem 0" },
  emptyText: { opacity: 0.45, fontSize: "0.9rem", margin: 0 },

  rosterGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "0.75rem" },
  rosterCard: {
    padding: "0.85rem 1rem",
    borderRadius: 8,
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    position: "relative",
  },
  inactiveBadge: {
    position: "absolute",
    top: 8,
    right: 8,
    fontSize: "0.65rem",
    fontWeight: 600,
    letterSpacing: "0.05em",
    padding: "0.1rem 0.4rem",
    borderRadius: 4,
    background: "rgba(255,255,255,0.08)",
    color: "rgba(255,255,255,0.55)",
  },

  table: { width: "100%", borderCollapse: "collapse" },
  tableHeadRow: { borderBottom: "1px solid rgba(255,255,255,0.1)" },
  th: { textAlign: "left", fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.55, padding: "0.6rem 0.5rem" },
  thRight: { textAlign: "right", fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.55, padding: "0.6rem 0.5rem" },
  tableRow: { borderBottom: "1px solid rgba(255,255,255,0.05)" },
  td: { padding: "0.7rem 0.5rem", fontSize: "0.9rem" },
  tdRight: { padding: "0.7rem 0.5rem", fontSize: "0.9rem", textAlign: "right" },
  resultPill: { display: "inline-block", minWidth: 24, textAlign: "center", fontWeight: 700, fontSize: "0.75rem", padding: "0.15rem 0.5rem", borderRadius: 4 },
};
