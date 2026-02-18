"use client";

import { useRouter, useSearchParams } from "next/navigation";
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

const LOL_CSU_STATS: LeagueStats = {
  team: {
    name: "CSU Vikes Green",
    game: "League of Legends",
    season: "Spring 2026",
    region: "Collegiate Midwest",
    overallRecord: "14-6",
    winRate: 70,
    averageGameTime: "30:42",
    goldDifferenceAt15: 1250,
    firstBloodRate: 65,
    firstTowerRate: 58,
    dragonControlRate: 61,
    heraldControlRate: 64,
    baronControlRate: 67,
    earlyGameRating: 8.4,
    midGameRating: 7.8,
    lateGameRating: 8.6,
    teamKDA: 3.12,
    averageKillsPerGame: 15.8,
    averageDeathsPerGame: 9.3,
    averageGoldPerMinute: 1845,
    averageVisionScorePerMinute: 3.4,
    preferredPlaystyle: "Strong early objective control with scaling teamfight focus",
    bestSide: "Blue",
    worstSide: "Red",
  },
  players: [
    { name: "VIKES 1", role: "Top", championPool: ["Aatrox", "Renekton", "Gnar", "Ornn"], gamesPlayed: 20, KDA: 2.9 },
    { name: "VIKES 2", role: "Jungle", championPool: ["Lee Sin", "Viego", "Sejuani", "Maokai"], gamesPlayed: 20, KDA: 3.8 },
    { name: "VIKES 3", role: "Mid", championPool: ["Orianna", "Ahri", "Syndra", "Taliyah"], gamesPlayed: 20, KDA: 4.1 },
    { name: "VIKES 4", role: "ADC", championPool: ["Jinx", "Aphelios", "Kai'Sa", "Xayah"], gamesPlayed: 20, KDA: 4.5 },
    { name: "VIKES 5", role: "Support", championPool: ["Nautilus", "Thresh", "Rakan", "Lulu"], gamesPlayed: 20, KDA: 4.8 },
  ],
  draftTrends: {
    mostBannedAgainst: ["Orianna", "Jinx"],
    flexPickRate: 18,
    redSideCounterPickWinRate: 74,
    averageDraftAdaptabilityRating: 8.3,
    earlyGameCompWinRate: 68,
    scalingCompWinRate: 73,
  },
  teamStrengths: [
    "Strong dragon stacking and objective setups",
    "High mid-jungle synergy",
    "Late game teamfight execution",
    "Strong vision denial around Baron",
  ],
  teamWeaknesses: [
    "Occasional overforce in early skirmishes",
    "Top lane vulnerable to heavy early dive comps",
    "Struggles against heavy split-push strategies",
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

export default function LeagueStatsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const teamQuery = params.get("team") ?? "CSU";

  const s = LOL_CSU_STATS;

  return (
    <main style={styles.container}>
      <div style={styles.headerRow}>
        <div>
          <h1 style={styles.title}>{s.team.name}</h1>
          <p style={styles.subtitle}>
            {s.team.game} • {s.team.season} • {s.team.region} • Team query: <strong>{teamQuery}</strong>
          </p>
        </div>

        <button style={styles.backBtn} onClick={() => router.push("/league")}>
          Back
        </button>
      </div>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Team Overview</h2>
        <div style={styles.kpiGrid}>
          <KPI label="Record" value={s.team.overallRecord} />
          <KPI label="Win Rate" value={`${s.team.winRate}%`} />
          <KPI label="Avg Game Time" value={s.team.averageGameTime} />
          <KPI label="Gold @15" value={s.team.goldDifferenceAt15} />
          <KPI label="First Blood" value={`${s.team.firstBloodRate}%`} />
          <KPI label="First Tower" value={`${s.team.firstTowerRate}%`} />
          <KPI label="Dragon Ctrl" value={`${s.team.dragonControlRate}%`} />
          <KPI label="Baron Ctrl" value={`${s.team.baronControlRate}%`} />
          <KPI label="Team KDA" value={s.team.teamKDA} />
        </div>

        <div style={styles.noteCard}>
          <div style={styles.noteTitle}>Preferred Playstyle</div>
          <div style={styles.noteText}>{s.team.preferredPlaystyle}</div>
          <div style={styles.noteMeta}>
            Best side: <strong>{s.team.bestSide}</strong> • Worst side: <strong>{s.team.worstSide}</strong>
          </div>
        </div>
      </section>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Players</h2>
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
      </section>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Draft Trends</h2>
        <div style={styles.kpiGrid}>
          <KPI label="Most Banned" value={s.draftTrends.mostBannedAgainst.join(", ")} />
          <KPI label="Flex Pick Rate" value={`${s.draftTrends.flexPickRate}%`} />
          <KPI label="Red-side Counter Win%" value={`${s.draftTrends.redSideCounterPickWinRate}%`} />
          <KPI label="Draft Adaptability" value={s.draftTrends.averageDraftAdaptabilityRating} />
          <KPI label="Early Comp Win%" value={`${s.draftTrends.earlyGameCompWinRate}%`} />
          <KPI label="Scaling Comp Win%" value={`${s.draftTrends.scalingCompWinRate}%`} />
        </div>
      </section>

      <section style={styles.card}>
        <h2 style={styles.sectionTitle}>Strengths & Weaknesses</h2>
        <div style={styles.twoCol}>
          <div style={styles.listCard}>
            <div style={styles.listTitle}>Strengths</div>
            <ul style={styles.ul}>
              {s.teamStrengths.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
          <div style={styles.listCard}>
            <div style={styles.listTitle}>Weaknesses</div>
            <ul style={styles.ul}>
              {s.teamWeaknesses.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
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

  noteCard: { marginTop: "0.85rem", padding: "0.85rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  noteTitle: { fontSize: "0.95rem", opacity: 0.9, fontWeight: 700 },
  noteText: { marginTop: "0.35rem", opacity: 0.9 },
  noteMeta: { marginTop: "0.35rem", opacity: 0.85 },

  table: { display: "grid", gap: "0.5rem" },
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
  th: { background: "rgba(255,255,255,0.08)", fontWeight: 700 },

  twoCol: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" },
  listCard: { padding: "0.9rem", borderRadius: 14, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(0,0,0,0.18)" },
  listTitle: { fontSize: "1.05rem", fontWeight: 700, marginBottom: "0.5rem" },
  ul: { margin: 0, paddingLeft: "1.1rem", opacity: 0.9, lineHeight: 1.5 },
};
