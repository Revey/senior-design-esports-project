"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { CSSProperties } from "react";

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
  win?: boolean;
};

type FrequencyEntry = { name: string; count: number };

type PlayerProfile = {
  slug: string;
  displayName: string;
  riotId: string;
  teamName: string;
  teamSlug: string;
  game: string;
  role: string;
  active: boolean;
  recentMatches: MatchStat[];
  frequency: FrequencyEntry[];
  frequencyField: "agent" | "champion";
};

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

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

  const isVal = player.game !== "lol";
  const accent = isVal ? "#ff4655" : "#c89b3c";
  const maxFreq = player.frequency[0]?.count ?? 1;

  return (
    <main style={s.container}>
      <div className="page-content">
        <Link href="/players" style={s.backLink}>← Back to players</Link>

        {/* Header */}
        <header style={{ ...s.header, borderColor: `${accent}55` }}>
          <div>
            <div style={s.nameRow}>
              <h1 style={s.title}>{player.displayName}</h1>
              <span
                style={{
                  ...s.gameBadge,
                  background: `${accent}22`,
                  color: accent,
                  borderColor: `${accent}88`,
                }}
              >
                {isVal ? "VALORANT" : "LEAGUE OF LEGENDS"}
              </span>
            </div>
            <p style={s.subtitle}>
              {player.role && (
                <>
                  <span style={{ color: accent, fontWeight: 600 }}>{player.role}</span>
                  <span style={{ opacity: 0.3, margin: "0 0.6rem" }}>·</span>
                </>
              )}
              {player.teamName ? (
                <Link
                  href={`/teams?slug=${player.teamSlug}`}
                  style={{ color: "white", textDecoration: "none", opacity: 0.8 }}
                >
                  {player.teamName}
                </Link>
              ) : (
                <span style={{ opacity: 0.5 }}>No team</span>
              )}
            </p>
            {player.riotId && (
              <p style={{ marginTop: "0.4rem", opacity: 0.5, fontSize: "0.85rem" }}>
                {player.riotId}
              </p>
            )}
          </div>
          <div>
            <span
              style={{
                display: "inline-block",
                padding: "0.3rem 0.8rem",
                borderRadius: 8,
                fontSize: "0.8rem",
                fontWeight: 600,
                background: player.active ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                color: player.active ? "#22c55e" : "#ef4444",
              }}
            >
              {player.active ? "Active" : "Inactive"}
            </span>
          </div>
        </header>

        {/* Agent / Champion frequency */}
        <section style={s.card}>
          <h2 style={s.sectionTitle}>{isVal ? "Agent pool" : "Champion pool"}</h2>
          {player.frequency.length === 0 ? (
            <p style={s.emptyText}>
              No {isVal ? "agent" : "champion"} data yet. Stats appear once matches are logged.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {player.frequency.slice(0, 8).map((f) => (
                <div key={f.name} style={s.freqRow}>
                  <div style={s.freqName}>{f.name}</div>
                  <div style={s.freqBarTrack}>
                    <div
                      style={{
                        ...s.freqBarFill,
                        width: `${(f.count / maxFreq) * 100}%`,
                        background: accent,
                      }}
                    />
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
          {player.recentMatches.length === 0 ? (
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
                    {isVal ? (
                      <th style={s.thRight}>ACS</th>
                    ) : (
                      <th style={s.thRight}>CS</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {player.recentMatches.map((m, i) => (
                    <tr key={`${m.matchId}-${i}`} style={s.tableRow}>
                      <td style={s.td}>
                        <span
                          style={{
                            ...s.resultPill,
                            background: m.win ? "#22c55e22" : "#ef444422",
                            color: m.win ? "#22c55e" : "#ef4444",
                          }}
                        >
                          {m.win ? "W" : "L"}
                        </span>
                      </td>
                      <td style={s.td}>{isVal ? (m.mapName ?? "—") : (m.role ?? "—")}</td>
                      <td style={s.td}>{isVal ? (m.agent ?? "—") : (m.champion ?? "—")}</td>
                      <td style={s.tdRight} className="tabular-nums">{m.kills ?? "—"}</td>
                      <td style={s.tdRight} className="tabular-nums">{m.deaths ?? "—"}</td>
                      <td style={s.tdRight} className="tabular-nums">{m.assists ?? "—"}</td>
                      <td style={s.tdRight} className="tabular-nums">
                        {isVal ? (m.acs ?? "—") : (m.cs ?? "—")}
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
  backLink: {
    color: "rgba(255,255,255,0.55)",
    textDecoration: "none",
    fontSize: "0.85rem",
    display: "inline-block",
    marginBottom: "1.25rem",
  },
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
  title: {
    fontSize: "clamp(1.8rem, 3.5vw, 2.6rem)",
    fontWeight: 800,
    letterSpacing: "-0.02em",
    margin: 0,
  },
  subtitle: { marginTop: "0.5rem", opacity: 0.8, fontSize: "1rem" },
  gameBadge: {
    fontSize: "0.7rem",
    fontWeight: 700,
    letterSpacing: "0.08em",
    padding: "0.3rem 0.7rem",
    borderRadius: 6,
    border: "1px solid",
  },
  card: {
    padding: "1.25rem 1.5rem",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.08)",
    background: "rgba(255,255,255,0.02)",
    marginBottom: "1.25rem",
  },
  sectionTitle: {
    fontSize: "0.8rem",
    fontWeight: 600,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    opacity: 0.55,
    margin: "0 0 1rem 0",
  },
  emptyText: { opacity: 0.45, fontSize: "0.9rem", margin: 0 },
  freqRow: { display: "grid", gridTemplateColumns: "120px 1fr 40px", alignItems: "center", gap: "0.8rem" },
  freqName: { fontSize: "0.9rem", fontWeight: 500 },
  freqBarTrack: { height: 10, borderRadius: 5, background: "rgba(255,255,255,0.06)", overflow: "hidden" },
  freqBarFill: { height: "100%", borderRadius: 5 },
  freqCount: { fontSize: "0.9rem", opacity: 0.7, textAlign: "right" },
  table: { width: "100%", borderCollapse: "collapse" },
  tableHeadRow: { borderBottom: "1px solid rgba(255,255,255,0.1)" },
  th: {
    textAlign: "left",
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    opacity: 0.55,
    padding: "0.6rem 0.5rem",
  },
  thRight: {
    textAlign: "right",
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    opacity: 0.55,
    padding: "0.6rem 0.5rem",
  },
  tableRow: { borderBottom: "1px solid rgba(255,255,255,0.05)" },
  td: { padding: "0.7rem 0.5rem", fontSize: "0.9rem" },
  tdRight: { padding: "0.7rem 0.5rem", fontSize: "0.9rem", textAlign: "right" },
  resultPill: {
    display: "inline-block",
    minWidth: 24,
    textAlign: "center",
    fontWeight: 700,
    fontSize: "0.75rem",
    padding: "0.15rem 0.5rem",
    borderRadius: 4,
  },
};