"use client";

import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";

type TeamRecord = { wins: number; losses: number };
type Team = {
  slug: string;
  name: string;
  school: string;
  game: string;
  record: TeamRecord;
  win_rate: number;
  rating: number;
  region: string;
  league_slug: string;
};

type GameFilter = "All" | "Valorant" | "League of Legends";
type SortField = "rating" | "win_rate" | "record.wins";

const GAME_TABS: { label: GameFilter; color: string }[] = [
  { label: "All", color: "#2563eb" },
  { label: "Valorant", color: "#ff4655" },
  { label: "League of Legends", color: "#c89b3c" },
];

const API = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function ratingColor(r: number): string {
  if (r >= 1800) return "#22c55e";
  if (r >= 1600) return "#eab308";
  return "#f97316";
}

function TeamsContent() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [game, setGame] = useState<GameFilter>("All");
  const [sortField, setSortField] = useState<SortField>("rating");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");

  useEffect(() => {
    setError(null);
    const params = new URLSearchParams({ sort: sortField, order: sortOrder, limit: "50" });
    if (game !== "All") params.set("game", game);

    fetch(`${API}/api/teams?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load teams (${r.status})`);
        return r.json() as Promise<Team[]>;
      })
      .then(setTeams)
      .catch((e: Error) => setError(e.message));
  }, [game, sortField, sortOrder]);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortOrder((o) => (o === "desc" ? "asc" : "desc"));
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  }

  function sortIndicator(field: SortField) {
    if (sortField !== field) return "";
    return sortOrder === "desc" ? " \u25BC" : " \u25B2";
  }

  const activeColor = GAME_TABS.find((t) => t.label === game)!.color;

  return (
    <main style={s.container}>
      <h1 style={s.title}>Team Rankings</h1>
      <p style={s.subtitle}>Collegiate esports team rankings</p>

      {/* Game filter tabs */}
      <div style={s.tabRow}>
        {GAME_TABS.map((tab) => {
          const active = game === tab.label;
          return (
            <button
              key={tab.label}
              onClick={() => setGame(tab.label)}
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

      {/* Rankings table */}
      <section style={{ ...s.card, borderColor: `${activeColor}55` }}>
        <div style={{ ...s.row, ...s.header }}>
          <div style={s.rankCol}>#</div>
          <div style={s.nameCol}>Team</div>
          <div style={s.schoolCol}>School</div>
          <div style={s.gameCol}>Game</div>
          <div style={{ ...s.statCol, cursor: "pointer" }} onClick={() => toggleSort("record.wins")}>
            Record{sortIndicator("record.wins")}
          </div>
          <div style={{ ...s.statCol, cursor: "pointer" }} onClick={() => toggleSort("win_rate")}>
            Win%{sortIndicator("win_rate")}
          </div>
          <div style={{ ...s.ratingCol, cursor: "pointer" }} onClick={() => toggleSort("rating")}>
            Rating{sortIndicator("rating")}
          </div>
        </div>

        {teams.length === 0 && !error && (
          <p style={{ padding: "1rem", opacity: 0.6 }}>Loading...</p>
        )}

        {teams.map((t, i) => (
          <div key={t.slug} style={s.row}>
            <div style={s.rankCol}>
              <span style={{ ...s.rankBadge, background: i < 3 ? activeColor : "rgba(255,255,255,0.08)" }}>
                {i + 1}
              </span>
            </div>
            <div style={s.nameCol}>
              <span style={{ fontWeight: 600 }}>{t.name}</span>
            </div>
            <div style={{ ...s.schoolCol, opacity: 0.75 }}>{t.school}</div>
            <div style={s.gameCol}>
              <span
                style={{
                  ...s.gameBadge,
                  background: t.game === "Valorant" ? "rgba(255,70,85,0.15)" : "rgba(200,155,60,0.15)",
                  color: t.game === "Valorant" ? "#ff4655" : "#c89b3c",
                }}
              >
                {t.game === "Valorant" ? "VAL" : "LoL"}
              </span>
            </div>
            <div style={s.statCol}>
              {t.record.wins}-{t.record.losses}
            </div>
            <div style={s.statCol}>{t.win_rate}%</div>
            <div style={s.ratingCol}>
              <span style={{ ...s.ratingBadge, color: ratingColor(t.rating) }}>{t.rating}</span>
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}

export default function TeamsPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" }}>Loading...</main>}>
      <TeamsContent />
    </Suspense>
  );
}

const s: Record<string, CSSProperties> = {
  container: { minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" },
  title: { fontSize: "2.2rem", margin: 0 },
  subtitle: { marginTop: "0.35rem", opacity: 0.7, marginBottom: "1.25rem" },

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
    background: "rgba(255,255,255,0.04)",
    borderRadius: 16,
    overflow: "hidden",
  },

  row: {
    display: "grid",
    gridTemplateColumns: "60px 1.8fr 1.5fr 80px 90px 80px 90px",
    gap: "0.75rem",
    padding: "0.85rem 1rem",
    alignItems: "center",
    borderBottom: "1px solid rgba(255,255,255,0.07)",
  },
  header: {
    background: "rgba(255,255,255,0.06)",
    fontWeight: 700,
    fontSize: "0.85rem",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    opacity: 0.8,
  },

  rankCol: { textAlign: "center" as const },
  rankBadge: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 32,
    height: 32,
    borderRadius: 8,
    fontWeight: 700,
    fontSize: "0.9rem",
  },
  nameCol: {},
  schoolCol: { fontSize: "0.9rem" },
  gameCol: {},
  gameBadge: {
    padding: "0.2rem 0.6rem",
    borderRadius: 6,
    fontSize: "0.8rem",
    fontWeight: 600,
  },
  statCol: { textAlign: "center" as const },
  ratingCol: { textAlign: "center" as const },
  ratingBadge: { fontWeight: 700, fontSize: "1.05rem" },
};
