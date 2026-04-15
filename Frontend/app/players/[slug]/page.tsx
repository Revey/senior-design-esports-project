"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { CSSProperties } from "react";

type PlayerStats = {
  kd?: number;
  acs?: number;
  adr?: number;
  hs_percent?: number;
  kda?: number;
  kills_per_game?: number;
  deaths_per_game?: number;
  assists_per_game?: number;
};

type MatchStat = {
  matchId?: string;
  game?: string;
  mapName?: string;
  teamName?: string;
  agent?: string;
  champion?: string;
  role?: string;
  kills?: number;
  deaths?: number;
  assists?: number;
  acs?: number;
  cs?: number;
  gold?: number;
  damage?: number;
  win?: boolean;
};

type FrequencyEntry = { name: string; count: number };

type PlayerProfile = {
  slug: string;
  name: string;
  team_name: string;
  team_slug: string;
  game: string;
  role: string;
  stats: PlayerStats;
  rating: number;
  recent_matches: MatchStat[];
  frequency: FrequencyEntry[];
  frequency_field: "agent" | "champion";
};

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

function ratingColor(r: number): string {
  if (r >= 1700) return "#22c55e";
  if (r >= 1500) return "#eab308";
  return "#f97316";
}

export default function PlayerProfilePage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug;
  const [player, setPlayer] = useState<PlayerProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setError(null);
    fetch(`${API}/api/players/${slug}`)
      .then((r) => {
        if (r.status === 404) throw new Error("Player not found");
        if (!r.ok) throw new Error(`Failed to load player (${r.status})`);
        return r.json() as Promise<PlayerProfile>;
      })
      .then(setPlayer)
      .catch((e: Error) => setError(e.message));
  }, [slug]);

  if (error) {
    return (
      <main style={s.container}>
        <div className="page-content">
          <Link href="/players" style={s.backLink}>← Back to players</Link>
          <h1 style={s.title}>{error}</h1>
        </div>
      </main>
    );
  }

  if (!player) {
    return (
      <main style={s.container}>
        <div className="page-content">
          <Link href="/players" style={s.backLink}>← Back to players</Link>
          <div className="skeleton-line" style={{ height: 48, marginTop: 16, width: "40%" }} />
          <div className="skeleton-line" style={{ height: 24, marginTop: 12, width: "25%" }} />
          <div className="skeleton-line" style={{ height: 200, marginTop: 24 }} />
        </div>
      </main>
    );
  }

  const isVal = player.game === "Valorant";
  const accent = isVal ? "#ff4655" : "#c89b3c";
  const maxFreq = player.frequency[0]?.count ?? 1;

  const statEntries: { label: string; value: string | number }[] = isVal
    ? [
        { label: "K/D", value: player.stats.kd ?? "-" },
        { label: "ACS", value: player.stats.acs ?? "-" },
        { label: "ADR", value: player.stats.adr ?? "-" },
        { label: "HS%", value: player.stats.hs_percent != null ? `${player.stats.hs_percent}%` : "-" },
      ]
    : [
        { label: "KDA", value: player.stats.kda ?? "-" },
        { label: "Kills/G", value: player.stats.kills_per_game ?? "-" },
        { label: "Deaths/G", value: player.stats.deaths_per_game ?? "-" },
        { label: "Assists/G", value: player.stats.assists_per_game ?? "-" },
      ];

  return (
    <main style={s.container}>
      <div className="page-content">
        <Link href="/players" style={s.backLink}>← Back to players</Link>

        {/* Header */}
        <header style={{ ...s.header, borderColor: `${accent}55` }}>
          <div>
            <div style={s.nameRow}>
              <h1 style={s.title}>{player.name}</h1>
              <span style={{ ...s.gameBadge, background: `${accent}22`, color: accent, borderColor: `${accent}88` }}>
                {isVal ? "VALORANT" : "LEAGUE OF LEGENDS"}
              </span>
            </div>
            <p style={s.subtitle}>
              <span style={{ color: accent, fontWeight: 600 }}>{player.role}</span>
              <span style={{ opacity: 0.3, margin: "0 0.6rem" }}>·</span>
              <Link href={`/teams?slug=${player.team_slug}`} style={{ color: "white", textDecoration: "none", opacity: 0.8 }}>
                {player.team_name}
              </Link>
            </p>
          </div>
          <div style={s.ratingBlock}>
            <div style={{ fontSize: "0.75rem", opacity: 0.5, letterSpacing: "0.08em" }}>RATING</div>
            <div style={{ fontSize: "2.4rem", fontWeight: 800, color: ratingColor(player.rating) }} className="tabular-nums">
              {player.rating}
            </div>
          </div>
        </header>

        {/* Career stats */}
        <section style={s.card}>
          <h2 style={s.sectionTitle}>Career stats</h2>
          <div style={s.statGrid}>
            {statEntries.map((stat) => (
              <div key={stat.label} style={s.statCell}>
                <div style={s.statLabel}>{stat.label}</div>
                <div style={s.statValue} className="tabular-nums">{stat.value}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Agent / Champion frequency */}
        <section style={s.card}>
          <h2 style={s.sectionTitle}>{isVal ? "Agent pool" : "Champion pool"}</h2>
          {player.frequency.length === 0 ? (
            <p style={s.emptyText}>No {isVal ? "agent" : "champion"} data yet. Stats appear once matches are logged.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {player.frequency.slice(0, 8).map((f) => (
                <div key={f.name} style={s.freqRow}>
                  <div style={s.freqName}>{f.name}</div>
                  <div style={s.freqBarTrack}>
                    <div style={{ ...s.freqBarFill, width: `${(f.count / maxFreq) * 100}%`, background: accent }} />
                  </div>
                  <div style={s.freqCount} className="tabular-nums">{f.count}</div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent matches */}
        <section style={s.card}>
          <h2 style={s.sectionTitle}>Recent matches</h2>
          {player.recent_matches.length === 0 ? (
            <p style={s.emptyText}>No logged matches yet.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={s.table}>
                <thead>
                  <tr style={s.tableHeadRow}>
                    <th style={s.th}>Result</th>
                    <th style={s.th}>{isVal ? "Map" : "Role"}</th>
                    <th style={s.th}>{isVal ? "Agent" : "Champion"}</th>
                    <th style={s.thRight}>K</th>
                    <th style={s.thRight}>D</th>
                    <th style={s.thRight}>A</th>
                    {isVal ? <th style={s.thRight}>ACS</th> : <th style={s.thRight}>CS</th>}
                  </tr>
                </thead>
                <tbody>
                  {player.recent_matches.map((m, i) => (
                    <tr key={`${m.matchId}-${i}`} style={s.tableRow}>
                      <td style={s.td}>
                        <span style={{ ...s.resultPill, background: m.win ? "#22c55e22" : "#ef444422", color: m.win ? "#22c55e" : "#ef4444" }}>
                          {m.win ? "W" : "L"}
                        </span>
                      </td>
                      <td style={s.td}>{isVal ? (m.mapName ?? "-") : (m.role ?? "-")}</td>
                      <td style={s.td}>{isVal ? (m.agent ?? "-") : (m.champion ?? "-")}</td>
                      <td style={s.tdRight} className="tabular-nums">{m.kills ?? "-"}</td>
                      <td style={s.tdRight} className="tabular-nums">{m.deaths ?? "-"}</td>
                      <td style={s.tdRight} className="tabular-nums">{m.assists ?? "-"}</td>
                      <td style={s.tdRight} className="tabular-nums">{isVal ? (m.acs ?? "-") : (m.cs ?? "-")}</td>
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
  subtitle: { marginTop: "0.5rem", opacity: 0.8, fontSize: "1rem" },
  gameBadge: {
    fontSize: "0.7rem",
    fontWeight: 700,
    letterSpacing: "0.08em",
    padding: "0.3rem 0.7rem",
    borderRadius: 6,
    border: "1px solid",
  },
  ratingBlock: { textAlign: "right" },

  card: {
    padding: "1.25rem 1.5rem",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.08)",
    background: "rgba(255,255,255,0.02)",
    marginBottom: "1.25rem",
  },
  sectionTitle: { fontSize: "0.8rem", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.55, margin: "0 0 1rem 0" },
  emptyText: { opacity: 0.45, fontSize: "0.9rem", margin: 0 },

  statGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "1rem" },
  statCell: { padding: "0.9rem 1rem", borderRadius: 8, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" },
  statLabel: { fontSize: "0.7rem", opacity: 0.5, letterSpacing: "0.08em", textTransform: "uppercase" },
  statValue: { fontSize: "1.6rem", fontWeight: 700, marginTop: "0.25rem" },

  freqRow: { display: "grid", gridTemplateColumns: "120px 1fr 40px", alignItems: "center", gap: "0.8rem" },
  freqName: { fontSize: "0.9rem", fontWeight: 500 },
  freqBarTrack: { height: 10, borderRadius: 5, background: "rgba(255,255,255,0.06)", overflow: "hidden" },
  freqBarFill: { height: "100%", borderRadius: 5 },
  freqCount: { fontSize: "0.9rem", opacity: 0.7, textAlign: "right" },

  table: { width: "100%", borderCollapse: "collapse" },
  tableHeadRow: { borderBottom: "1px solid rgba(255,255,255,0.1)" },
  th: { textAlign: "left", fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.55, padding: "0.6rem 0.5rem" },
  thRight: { textAlign: "right", fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.55, padding: "0.6rem 0.5rem" },
  tableRow: { borderBottom: "1px solid rgba(255,255,255,0.05)" },
  td: { padding: "0.7rem 0.5rem", fontSize: "0.9rem" },
  tdRight: { padding: "0.7rem 0.5rem", fontSize: "0.9rem", textAlign: "right" },
  resultPill: { display: "inline-block", minWidth: 24, textAlign: "center", fontWeight: 700, fontSize: "0.75rem", padding: "0.15rem 0.5rem", borderRadius: 4 },
};
