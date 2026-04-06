"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";

type MapInfo = { record: string; winRate: number };

type ValorantTeam = {
  name: string;
  game: string;
  season: string;
  overallRecord: string;
  winRate: number;
  roundWinRate: number;
  pistolRoundWinRate: number;
  attackWinRate: number;
  defenseWinRate: number;
  averageTeamACS: number;
  averageTeamKD: number;
  averageHSPercent: number;
  averageDamageDelta: string;
  bestMap: string;
  worstMap: string;
  mapPool: Record<string, MapInfo>;
};

type ValorantPlayer = {
  name: string;
  role: string;
  KD: number;
  ACS: number;
  HSPercent: number;
  ADR: number;
  damageDelta: string;
};

type ValorantStats = {
  team: ValorantTeam;
  players: ValorantPlayer[];
};

type Tab = "Overall" | "CVAL";

const TABS: { label: Tab; color: string; file: string }[] = [
  { label: "Overall", color: "#2563eb", file: "CSUValGreen" },
  { label: "CVAL",    color: "#ca8a04", file: "CSUValCval" },
];

type KPIProps = { label: string; value: string | number };

function KPI({ label, value }: KPIProps) {
  return (
    <div style={styles.kpi}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={styles.kpiValue}>{value}</div>
    </div>
  );
}

function ValorantStatsContent() {
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<Tab>("Overall");
  const [stats, setStats] = useState<ValorantStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeTabConfig = TABS.find((t) => t.label === activeTab)!;
  const activeColor = activeTabConfig.color;
  const activeFile = activeTabConfig.file;

  useEffect(() => {
    setStats(null);
    setError(null);

    fetch(`/teams/${activeFile}.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`Could not load /teams/${activeFile}.json (${res.status})`);
        return res.json() as Promise<ValorantStats>;
      })
      .then(setStats)
      .catch((err: Error) => setError(err.message));
  }, [activeFile]);

  if (error) {
    return (
      <main style={styles.container}>
        <p style={{ color: "#f87171" }}>⚠️ {error}</p>
        <button style={styles.backBtn} onClick={() => router.push("/valorant")}>
          Back
        </button>
      </main>
    );
  }

  return (
    <main style={styles.container}>
      {/* ── Header ───────────────────────────────────── */}
      <div style={styles.headerRow}>
        <div>
          <h1 style={styles.title}>{stats?.team.name ?? "Loading…"}</h1>
          {stats && (
            <p style={styles.subtitle}>
              {stats.team.game} • {stats.team.season}
            </p>
          )}
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button style={styles.rsoBtn} onClick={() => router.push("/valorant/auth")}>
            Connect Riot Account
          </button>
          <button style={styles.backBtn} onClick={() => router.push("/valorant")}>
            Back
          </button>
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────────────── */}
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

      {/* ── Loading ──────────────────────────────────── */}
      {!stats && !error && (
        <p style={{ opacity: 0.7, marginTop: "1.5rem" }}>Loading stats…</p>
      )}

      {stats && (() => {
        const { team, players } = stats;
        return (
          <>
            {/* ── Team Overview ──────────────────────── */}
            <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
              <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Team Overview</h2>
              <div style={styles.kpiGrid}>
                <KPI label="Record"       value={team.overallRecord} />
                <KPI label="Win Rate"     value={`${team.winRate}%`} />
                <KPI label="Round Win%"   value={`${team.roundWinRate}%`} />
                <KPI label="Pistol Win%"  value={`${team.pistolRoundWinRate}%`} />
                <KPI label="Atk Win%"     value={`${team.attackWinRate}%`} />
                <KPI label="Def Win%"     value={`${team.defenseWinRate}%`} />
                <KPI label="Avg Team ACS" value={team.averageTeamACS} />
                <KPI label="Avg Team K/D" value={team.averageTeamKD} />
                <KPI label="Avg HS%"      value={`${team.averageHSPercent}%`} />
                <KPI label="Damage Δ"     value={team.averageDamageDelta} />
              </div>
              <div style={styles.row2}>
                <div style={styles.smallCard}>
                  <div style={styles.smallTitle}>Best Map</div>
                  <div style={styles.smallValue}>{team.bestMap}</div>
                </div>
                <div style={styles.smallCard}>
                  <div style={styles.smallTitle}>Worst Map</div>
                  <div style={styles.smallValue}>{team.worstMap}</div>
                </div>
              </div>
            </section>

            {/* ── Map Pool ───────────────────────────── */}
            <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
              <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Map Pool</h2>
              <div style={styles.mapGrid}>
                {Object.entries(team.mapPool).map(([map, info]) => (
                  <div key={map} style={styles.mapItem}>
                    <div style={styles.mapName}>{map}</div>
                    <div style={styles.mapMeta}>{info.record}</div>
                    <div style={styles.mapMeta}>{info.winRate}%</div>
                  </div>
                ))}
              </div>
            </section>

            {/* ── Players ────────────────────────────── */}
            <section style={{ ...styles.card, borderColor: `${activeColor}55` }}>
              <h2 style={{ ...styles.sectionTitle, color: activeColor }}>Players</h2>
              <div style={styles.table}>
                <div style={{ ...styles.tr, ...styles.th }}>
                  <div>Name</div>
                  <div>Role</div>
                  <div>K/D</div>
                  <div>ACS</div>
                  <div>HS%</div>
                  <div>ADR</div>
                  <div>DMG Δ</div>
                </div>
                {players.map((p) => (
                  <div key={p.name} style={styles.tr}>
                    <div>{p.name}</div>
                    <div style={{ opacity: 0.9 }}>{p.role}</div>
                    <div>{p.KD}</div>
                    <div>{p.ACS}</div>
                    <div>{p.HSPercent}</div>
                    <div>{p.ADR}</div>
                    <div>{p.damageDelta}</div>
                  </div>
                ))}
              </div>
            </section>
          </>
        );
      })()}
    </main>
  );
}

export default function ValorantStatsPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" }}>Loading…</main>}>
      <ValorantStatsContent />
    </Suspense>
  );
}

const styles: Record<string, CSSProperties> = {
  container:    { minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" },
  headerRow:    { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", marginBottom: "1.25rem" },
  title:        { fontSize: "2.2rem", margin: 0 },
  subtitle:     { marginTop: "0.35rem", opacity: 0.85 },
  backBtn:      { padding: "0.7rem 1rem", borderRadius: 12, border: "none", cursor: "pointer", background: "#2563eb", color: "white" },
  rsoBtn:       { padding: "0.7rem 1rem", borderRadius: 12, border: "none", cursor: "pointer", background: "#dc2626", color: "white", fontWeight: 600 },

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

  row2:         { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", marginTop: "0.75rem" },
  smallCard:    { padding: "0.75rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  smallTitle:   { fontSize: "0.9rem", opacity: 0.85 },
  smallValue:   { fontSize: "1.2rem", marginTop: "0.2rem" },

  mapGrid:      { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "0.75rem" },
  mapItem:      { padding: "0.75rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  mapName:      { fontSize: "1.05rem", fontWeight: 600 },
  mapMeta:      { opacity: 0.85, marginTop: "0.15rem" },

  table:        { display: "grid", gap: "0.5rem" },
  tr: {
    display: "grid",
    gridTemplateColumns: "1.6fr 1fr 0.6fr 0.6fr 0.6fr 0.6fr 0.7fr",
    gap: "0.75rem",
    padding: "0.75rem",
    borderRadius: 14,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(0,0,0,0.18)",
    alignItems: "center",
  },
  th:           { background: "rgba(255,255,255,0.08)", fontWeight: 700 },
};
