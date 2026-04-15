"use client";

import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";

type Standing = {
  rank: number;
  team_name: string;
  team_slug: string;
  wins: number;
  losses: number;
  win_rate: number;
};

type League = {
  slug: string;
  name: string;
  abbreviation: string;
  game: string;
  season: string;
  description: string;
  standings: Standing[];
};

type Tab = "cval" | "clol";

const TABS: { slug: Tab; label: string; color: string }[] = [
  { slug: "cval", label: "CVAL", color: "#ff4655" },
  { slug: "clol", label: "CLoL", color: "#c89b3c" },
];

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

function LeaguesContent() {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("cval");

  useEffect(() => {
    fetch(`${API}/api/leagues`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load leagues (${r.status})`);
        return r.json() as Promise<League[]>;
      })
      .then(setLeagues)
      .catch((e: Error) => setError(e.message));
  }, []);

  const league = leagues.find((l) => l.slug === activeTab);
  const tabConfig = TABS.find((t) => t.slug === activeTab)!;
  const activeColor = tabConfig.color;

  return (
    <main style={s.container}>
      <div className="page-content">
      <h1 style={s.title}>Collegiate esports leagues</h1>
      <p style={s.subtitle}>Official competitive leagues for collegiate teams</p>

      {/* League tabs */}
      <div style={s.tabRow}>
        {TABS.map((tab) => {
          const active = activeTab === tab.slug;
          return (
            <button
              key={tab.slug}
              onClick={() => setActiveTab(tab.slug)}
              style={{
                ...s.tabBtn,
                background: active ? tab.color : "rgba(255,255,255,0.07)",
                color: active ? "white" : "rgba(255,255,255,0.5)",
                borderColor: active ? tab.color : "rgba(255,255,255,0.12)",
                boxShadow: active ? `0 0 14px ${tab.color}66` : "none",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {error && <p style={{ color: "#f87171" }}>{error}</p>}

      {!league && !error && leagues.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <div className="skeleton-line" style={{ height: "110px" }} />
          <div className="skeleton-line" style={{ height: "240px" }} />
        </div>
      )}

      {!league && !error && leagues.length > 0 && (
        <div style={{ padding: "2.5rem 1rem", textAlign: "center", opacity: 0.5 }}>
          No data for this league yet.
        </div>
      )}

      {league && (
        <>
          {/* League info card */}
          <section style={{ ...s.card, borderColor: `${activeColor}55` }}>
            <div style={s.leagueHeader}>
              <div>
                <h2 style={{ ...s.leagueName, color: activeColor }}>{league.name}</h2>
                <p style={s.leagueMeta}>
                  {league.game} &bull; {league.season}
                </p>
              </div>
              <div style={{ ...s.badge, background: `${activeColor}22`, color: activeColor }}>
                {league.abbreviation}
              </div>
            </div>
            <p style={s.description}>{league.description}</p>
          </section>

          {/* Standings */}
          <section style={{ ...s.card, borderColor: `${activeColor}55`, marginTop: "1rem" }}>
            <h3 style={{ ...s.sectionTitle, color: activeColor }}>Standings</h3>

            <div style={s.standingsHeader}>
              <div style={s.rankCol}>#</div>
              <div style={s.teamCol}>Team</div>
              <div style={s.statCol}>W</div>
              <div style={s.statCol}>L</div>
              <div style={s.statCol}>Win%</div>
            </div>

            {league.standings.map((st) => (
              <div
                key={st.team_slug}
                className="data-row row-enter"
                style={{
                  ...s.standingsRow,
                  borderLeft: st.rank <= 3 ? `3px solid ${activeColor}` : "3px solid transparent",
                  animationDelay: `${st.rank * 0.04}s`,
                }}
              >
                <div style={s.rankCol}>
                  <span
                    style={{
                      ...s.rankBadge,
                      background: st.rank <= 3 ? activeColor : "rgba(255,255,255,0.08)",
                    }}
                  >
                    {st.rank}
                  </span>
                </div>
                <div style={{ ...s.teamCol, fontWeight: 600 }}>{st.team_name}</div>
                <div className="tabular-nums" style={s.statCol}>{st.wins}</div>
                <div className="tabular-nums" style={s.statCol}>{st.losses}</div>
                <div className="tabular-nums" style={s.statCol}>
                  <span
                    style={{
                      color: st.win_rate >= 60 ? "#22c55e" : st.win_rate >= 50 ? "#eab308" : "#f87171",
                      fontWeight: 600,
                    }}
                  >
                    {st.win_rate}%
                  </span>
                </div>
              </div>
            ))}
          </section>
        </>
      )}
      </div>
    </main>
  );
}

export default function LeaguesPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" }} />}>
      <LeaguesContent />
    </Suspense>
  );
}

const s: Record<string, CSSProperties> = {
  container: { minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" },
  title: { fontSize: "clamp(1.6rem, 3vw, 2.2rem)", fontWeight: 700, letterSpacing: "-0.02em", margin: 0 },
  subtitle: { marginTop: "0.35rem", opacity: 0.55, marginBottom: "1.5rem", fontSize: "0.95rem" },

  tabRow: { display: "flex", gap: "0.6rem", marginBottom: "1.25rem", flexWrap: "wrap" },
  tabBtn: {
    padding: "0.55rem 1.5rem",
    borderRadius: 10,
    border: "1px solid",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: "0.95rem",
    transition: "background 0.15s, color 0.15s, box-shadow 0.15s",
  },

  card: {
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: "1.25rem",
  },

  leagueHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "0.75rem",
  },
  leagueName: { fontSize: "1.4rem", margin: 0 },
  leagueMeta: { marginTop: "0.3rem", opacity: 0.7, fontSize: "0.95rem" },
  badge: {
    padding: "0.4rem 1rem",
    borderRadius: 10,
    fontWeight: 700,
    fontSize: "1.1rem",
    letterSpacing: "0.05em",
  },
  description: { opacity: 0.8, lineHeight: 1.6, margin: 0 },

  sectionTitle: { fontSize: "1.15rem", margin: "0 0 0.75rem 0" },

  standingsHeader: {
    display: "grid",
    gridTemplateColumns: "60px 1fr 60px 60px 80px",
    gap: "0.75rem",
    padding: "0.6rem 0.75rem",
    background: "rgba(255,255,255,0.06)",
    borderRadius: 10,
    fontWeight: 700,
    fontSize: "0.8rem",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    opacity: 0.7,
    marginBottom: "0.35rem",
  },
  standingsRow: {
    display: "grid",
    gridTemplateColumns: "60px 1fr 60px 60px 80px",
    gap: "0.75rem",
    padding: "0.75rem",
    alignItems: "center",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    transition: "background 0.12s",
  },

  rankCol: { textAlign: "center" as const },
  rankBadge: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 30,
    height: 30,
    borderRadius: 8,
    fontWeight: 700,
    fontSize: "0.85rem",
  },
  teamCol: {},
  statCol: { textAlign: "center" as const },
};
