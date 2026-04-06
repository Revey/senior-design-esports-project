"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";

type Team = {
  name: string;
  game: string;
  season: string;
  region: string;
  overallRecord: string;
  winRate: number;
  averageGameTime: string;
  goldDifferenceAt15: number;
  firstBloodRate: number;
  firstTowerRate: number;
  dragonControlRate: number;
  heraldControlRate: number;
  baronControlRate: number;
  earlyGameRating: number;
  midGameRating: number;
  lateGameRating: number;
  teamKDA: number;
  averageKillsPerGame: number;
  averageDeathsPerGame: number;
  averageGoldPerMinute: number;
  averageVisionScorePerMinute: number;
  preferredPlaystyle: string;
  bestSide: string;
  worstSide: string;
};

type Player = {
  name: string;
  role: string;
  championPool: string[];
  gamesPlayed: number;
  KDA: number;
};

type DraftTrends = {
  mostBannedAgainst: string[];
  flexPickRate: number;
  redSideCounterPickWinRate: number;
  averageDraftAdaptabilityRating: number;
  earlyGameCompWinRate: number;
  scalingCompWinRate: number;
};

type LeagueStats = {
  team: Team;
  players: Player[];
  draftTrends: DraftTrends;
  teamStrengths: string[];
  teamWeaknesses: string[];
};

type Tab = "Overall" | "CLoL";

const TABS: { label: Tab; color: string; file: string }[] = [
  { label: "Overall", color: "#2563eb", file: "CSULol" },
  { label: "CLoL",    color: "#dc2626", file: "CSULolClol" },
];

const NA_STATS: LeagueStats = {
  team: {
    name: "N/A", game: "N/A", season: "N/A", region: "N/A",
    overallRecord: "N/A", winRate: 0, averageGameTime: "N/A",
    goldDifferenceAt15: 0, firstBloodRate: 0, firstTowerRate: 0,
    dragonControlRate: 0, heraldControlRate: 0, baronControlRate: 0,
    earlyGameRating: 0, midGameRating: 0, lateGameRating: 0,
    teamKDA: 0, averageKillsPerGame: 0, averageDeathsPerGame: 0,
    averageGoldPerMinute: 0, averageVisionScorePerMinute: 0,
    preferredPlaystyle: "N/A", bestSide: "N/A", worstSide: "N/A",
  },
  players: [],
  draftTrends: {
    mostBannedAgainst: [], flexPickRate: 0, redSideCounterPickWinRate: 0,
    averageDraftAdaptabilityRating: 0, earlyGameCompWinRate: 0, scalingCompWinRate: 0,
  },
  teamStrengths: ["N/A"],
  teamWeaknesses: ["N/A"],
};

type KPIProps = { label: string; value: string | number };

function KPI({ label, value }: KPIProps) {
  return (
    <div style={styles.kpi}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={styles.kpiValue}>{value}</div>
    </div>
  );
}

function LeagueStatsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const teamQuery = params.get("team") ?? "CSU";

  const [activeTab, setActiveTab] = useState<Tab>("Overall");
  const [s, setS] = useState<LeagueStats | null>(null);

  const activeColor = TABS.find((t) => t.label === activeTab)!.color;
  const activeFile  = TABS.find((t) => t.label === activeTab)!.file;

  useEffect(() => {
    setS(null);

    fetch(`/teams/${activeFile}.json`)
      .then((res) => {
        if (!res.ok) throw new Error("not found");
        return res.json() as Promise<LeagueStats>;
      })
      .then(setS)
      .catch(() => setS(NA_STATS));
  }, [activeFile]);

  const naMode = s?.team.name === "N/A";

  return (
    <main style={styles.container}>
      {/* ── Header ─────────────────────────────────── */}
      <div style={styles.headerRow}>
        <div>
          <h1 style={styles.title}>
            {!s ? "Loading…" : naMode ? "CSU Vikes Green" : s.team.name}
          </h1>
          {s && !naMode && (
            <p style={styles.subtitle}>
              {s.team.game} • {s.team.season} • {s.team.region} • Team query: <strong>{teamQuery}</strong>
            </p>
          )}
        </div>
        <button style={styles.backBtn} onClick={() => router.push("/league")}>
          Back
        </button>
      </div>

      {/* ── Tabs ───────────────────────────────────── */}
      <div style={styles.tabRow}>
        {TABS.map((tab) => {
          const isActive = activeTab === tab.label;
          return (
            <button
              key={tab.label}
              onClick={() => setActiveTab(tab.label)}
              style={{
                ...styles.tabBtn,
                background:  isActive ? tab.color : "rgba(255,255,255,0.07)",
                color:       isActive ? "white"   : "rgba(255,255,255,0.5)",
                borderColor: isActive ? tab.color : "rgba(255,255,255,0.12)",
                boxShadow:   isActive ? `0 0 14px ${tab.color}66` : "none",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Loading ────────────────────────────────── */}
      {!s && <p style={{ opacity: 0.6, marginTop: "1.5rem" }}>Loading stats…</p>}

      {s && (
        <>
          {/* No-data banner */}
          {naMode && (
            <div style={{ ...styles.card, borderColor: `${activeColor}55`, opacity: 0.7 }}>
              <p style={{ margin: 0 }}>No data available for this league yet.</p>
            </div>
          )}

          {/* ── Team Overview ──────────────────────── */}
          <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
            <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Team Overview</h2>
            <div style={styles.kpiGrid}>
              <KPI label="Record"        value={naMode ? "N/A" : s.team.overallRecord} />
              <KPI label="Win Rate"      value={naMode ? "N/A" : `${s.team.winRate}%`} />
              <KPI label="Avg Game Time" value={naMode ? "N/A" : s.team.averageGameTime} />
              <KPI label="Gold @15"      value={naMode ? "N/A" : s.team.goldDifferenceAt15} />
              <KPI label="First Blood"   value={naMode ? "N/A" : `${s.team.firstBloodRate}%`} />
              <KPI label="First Tower"   value={naMode ? "N/A" : `${s.team.firstTowerRate}%`} />
              <KPI label="Dragon Ctrl"   value={naMode ? "N/A" : `${s.team.dragonControlRate}%`} />
              <KPI label="Baron Ctrl"    value={naMode ? "N/A" : `${s.team.baronControlRate}%`} />
              <KPI label="Team KDA"      value={naMode ? "N/A" : s.team.teamKDA} />
            </div>
            <div style={styles.noteCard}>
              <div style={styles.noteTitle}>Preferred Playstyle</div>
              <div style={styles.noteText}>{naMode ? "N/A" : s.team.preferredPlaystyle}</div>
              <div style={styles.noteMeta}>
                Best side: <strong>{naMode ? "N/A" : s.team.bestSide}</strong> • Worst side:{" "}
                <strong>{naMode ? "N/A" : s.team.worstSide}</strong>
              </div>
            </div>
          </section>

          {/* ── Players ────────────────────────────── */}
          <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
            <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Players</h2>
            {naMode ? (
              <p style={{ opacity: 0.6, margin: 0 }}>N/A</p>
            ) : (
              <div style={styles.table}>
                <div style={{ ...styles.trLeague, ...styles.th }}>
                  <div>Name</div>
                  <div>Role</div>
                  <div>KDA</div>
                  <div>Champion Pool</div>
                </div>
                {s.players.map((p) => (
                  <div key={p.name} style={styles.trLeague}>
                    <div>{p.name}</div>
                    <div style={{ opacity: 0.9 }}>{p.role}</div>
                    <div>{p.KDA}</div>
                    <div style={{ opacity: 0.9 }}>{p.championPool.join(", ")}</div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ── Draft Trends ───────────────────────── */}
          <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
            <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Draft Trends</h2>
            <div style={styles.kpiGrid}>
              <KPI label="Most Banned"          value={naMode ? "N/A" : s.draftTrends.mostBannedAgainst.join(", ")} />
              <KPI label="Flex Pick Rate"        value={naMode ? "N/A" : `${s.draftTrends.flexPickRate}%`} />
              <KPI label="Red-side Counter Win%" value={naMode ? "N/A" : `${s.draftTrends.redSideCounterPickWinRate}%`} />
              <KPI label="Draft Adaptability"    value={naMode ? "N/A" : s.draftTrends.averageDraftAdaptabilityRating} />
              <KPI label="Early Comp Win%"       value={naMode ? "N/A" : `${s.draftTrends.earlyGameCompWinRate}%`} />
              <KPI label="Scaling Comp Win%"     value={naMode ? "N/A" : `${s.draftTrends.scalingCompWinRate}%`} />
            </div>
          </section>

          {/* ── Strengths & Weaknesses ─────────────── */}
          <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
            <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Strengths & Weaknesses</h2>
            <div style={styles.twoCol}>
              <div style={styles.listCard}>
                <div style={styles.listTitle}>Strengths</div>
                <ul style={styles.ul}>
                  {s.teamStrengths.map((x) => <li key={x}>{x}</li>)}
                </ul>
              </div>
              <div style={styles.listCard}>
                <div style={styles.listTitle}>Weaknesses</div>
                <ul style={styles.ul}>
                  {s.teamWeaknesses.map((x) => <li key={x}>{x}</li>)}
                </ul>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export default function LeagueStatsPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" }}>Loading…</main>}>
      <LeagueStatsContent />
    </Suspense>
  );
}

const styles: Record<string, CSSProperties> = {
  container:    { minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" },
  headerRow:    { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", marginBottom: "1.25rem" },
  title:        { fontSize: "2.2rem", margin: 0 },
  subtitle:     { marginTop: "0.35rem", opacity: 0.85 },
  backBtn:      { padding: "0.7rem 1rem", borderRadius: 12, border: "none", cursor: "pointer", background: "#2563eb", color: "white" },

  tabRow:       { display: "flex", gap: "0.6rem", marginBottom: "1.25rem", flexWrap: "wrap" },
  tabBtn:       {
    padding: "0.55rem 1.5rem",
    borderRadius: 10,
    border: "1px solid",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: "0.95rem",
    transition: "background 0.15s, color 0.15s, box-shadow 0.15s",
  },

  card:         { border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.06)", borderRadius: 16, padding: "1.25rem", marginTop: "1rem" },
  sectionTitle: { fontSize: "1.2rem", marginTop: 0, marginBottom: "0.75rem" },

  kpiGrid:      { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "0.75rem" },
  kpi:          { padding: "0.75rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  kpiLabel:     { fontSize: "0.9rem", opacity: 0.85 },
  kpiValue:     { fontSize: "1.15rem", marginTop: "0.2rem" },

  noteCard:     { marginTop: "0.85rem", padding: "0.85rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  noteTitle:    { fontSize: "0.95rem", opacity: 0.9, fontWeight: 700 },
  noteText:     { marginTop: "0.35rem", opacity: 0.9 },
  noteMeta:     { marginTop: "0.35rem", opacity: 0.85 },

  table:        { display: "grid", gap: "0.5rem" },
  trLeague: {
    display: "grid",
    gridTemplateColumns: "1.2fr 0.7fr 0.5fr 2.2fr",
    gap: "0.75rem",
    padding: "0.75rem",
    borderRadius: 14,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(0,0,0,0.18)",
    alignItems: "center",
  },
  th:           { background: "rgba(255,255,255,0.08)", fontWeight: 700 },

  twoCol:       { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" },
  listCard:     { padding: "0.9rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  listTitle:    { fontSize: "1.05rem", fontWeight: 700, marginBottom: "0.5rem" },
  ul:           { margin: 0, paddingLeft: "1.1rem", opacity: 0.9, lineHeight: 1.5 },
};