"use client";

import { useRouter, useSearchParams } from "next/navigation";
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

const VALORANT_CSU_STATS: ValorantStats = {
  team: {
    name: "CSU Vikes Green",
    game: "Valorant",
    season: "Spring 2026",
    overallRecord: "18-7",
    winRate: 72,
    roundWinRate: 54.8,
    pistolRoundWinRate: 61.2,
    attackWinRate: 52.3,
    defenseWinRate: 57.1,
    averageTeamACS: 213.4,
    averageTeamKD: 1.08,
    averageHSPercent: 24.6,
    averageDamageDelta: "+8.3",
    bestMap: "Ascent",
    worstMap: "Icebox",
    mapPool: {
      Ascent: { record: "6-1", winRate: 85.7 },
      Bind: { record: "4-2", winRate: 66.7 },
      Haven: { record: "3-1", winRate: 75.0 },
      Split: { record: "3-2", winRate: 60.0 },
      Icebox: { record: "2-4", winRate: 33.3 },
    },
  },
  players: [
    { name: "VIKES Lian", role: "Smokes", KD: 1.02, ACS: 198.5, HSPercent: 22.1, ADR: 135.4, damageDelta: "+4.7" },
    { name: "VIKES N0ths", role: "Initiator", KD: 1.05, ACS: 205.3, HSPercent: 23.7, ADR: 142.8, damageDelta: "+6.2" },
    { name: "VIKES Kamino", role: "Flex", KD: 1.1, ACS: 220.7, HSPercent: 25.9, ADR: 148.3, damageDelta: "+9.5" },
    { name: "VIKES wyyu", role: "Duelist", KD: 1.21, ACS: 248.9, HSPercent: 27.4, ADR: 162.6, damageDelta: "+14.8" },
    { name: "VIKES Exquisitely", role: "Sentinel", KD: 1.03, ACS: 193.6, HSPercent: 23.8, ADR: 130.2, damageDelta: "+3.4" },
  ],
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

export default function ValorantStatsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const teamQuery = params.get("team") ?? "CSU";

  const s = VALORANT_CSU_STATS;

  return (
    <main style={styles.container}>
      <div style={styles.headerRow}>
        <div>
          <h1 style={styles.title}>{s.team.name}</h1>
          <p style={styles.subtitle}>
            {s.team.game} • {s.team.season} • Team query: <strong>{teamQuery}</strong>
          </p>
        </div>

        <button style={styles.backBtn} onClick={() => router.push("/valorant")}>
          Back
        </button>
      </div>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Team Overview</h2>
        <div style={styles.kpiGrid}>
          <KPI label="Record" value={s.team.overallRecord} />
          <KPI label="Win Rate" value={`${s.team.winRate}%`} />
          <KPI label="Round Win%" value={`${s.team.roundWinRate}%`} />
          <KPI label="Pistol Win%" value={`${s.team.pistolRoundWinRate}%`} />
          <KPI label="Atk Win%" value={`${s.team.attackWinRate}%`} />
          <KPI label="Def Win%" value={`${s.team.defenseWinRate}%`} />
          <KPI label="Avg Team ACS" value={s.team.averageTeamACS} />
          <KPI label="Avg Team K/D" value={s.team.averageTeamKD} />
          <KPI label="Avg HS%" value={`${s.team.averageHSPercent}%`} />
          <KPI label="Damage Δ" value={s.team.averageDamageDelta} />
        </div>

        <div style={styles.row2}>
          <div style={styles.smallCard}>
            <div style={styles.smallTitle}>Best Map</div>
            <div style={styles.smallValue}>{s.team.bestMap}</div>
          </div>
          <div style={styles.smallCard}>
            <div style={styles.smallTitle}>Worst Map</div>
            <div style={styles.smallValue}>{s.team.worstMap}</div>
          </div>
        </div>
      </section>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Map Pool</h2>
        <div style={styles.mapGrid}>
          {Object.entries(s.team.mapPool).map(([map, info]) => (
            <div key={map} style={styles.mapItem}>
              <div style={styles.mapName}>{map}</div>
              <div style={styles.mapMeta}>{info.record}</div>
              <div style={styles.mapMeta}>{info.winRate}%</div>
            </div>
          ))}
        </div>
      </section>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Players</h2>
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

          {s.players.map((p) => (
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
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  container: { minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" },
  headerRow: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", marginBottom: "1.25rem" },
  title: { fontSize: "2.2rem", margin: 0 },
  subtitle: { marginTop: "0.35rem", opacity: 0.85 },
  backBtn: { padding: "0.7rem 1rem", borderRadius: 12, border: "none", cursor: "pointer", background: "#2563eb", color: "white" },

  card: { border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.06)", borderRadius: 16, padding: "1.25rem", marginTop: "1rem" },
  sectionTitle: { fontSize: "1.2rem", marginTop: 0, marginBottom: "0.75rem" },

  kpiGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "0.75rem" },
  kpi: { padding: "0.75rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  kpiLabel: { fontSize: "0.9rem", opacity: 0.85 },
  kpiValue: { fontSize: "1.15rem", marginTop: "0.2rem" },

  row2: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", marginTop: "0.75rem" },
  smallCard: { padding: "0.75rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  smallTitle: { fontSize: "0.9rem", opacity: 0.85 },
  smallValue: { fontSize: "1.2rem", marginTop: "0.2rem" },

  mapGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "0.75rem" },
  mapItem: { padding: "0.75rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  mapName: { fontSize: "1.05rem", fontWeight: 600 },
  mapMeta: { opacity: 0.85, marginTop: "0.15rem" },

  table: { display: "grid", gap: "0.5rem" },
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
  th: { background: "rgba(255,255,255,0.08)", fontWeight: 700 },
};
