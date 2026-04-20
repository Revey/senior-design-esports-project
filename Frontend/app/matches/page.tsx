"use client";

import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";

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
};

type MatchResp = {
  items: Match[];
  total: number;
  page: number;
  limit: number;
};

type GameFilter = "All" | "Valorant" | "League of Legends";

const GAME_TABS: { label: GameFilter; color: string }[] = [
  { label: "All", color: "#2563eb" },
  { label: "Valorant", color: "#ff4655" },
  { label: "League of Legends", color: "#c89b3c" },
];

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
const PER_PAGE = 20;

function formatDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function MatchesContent() {
  const [data, setData] = useState<MatchResp | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [game, setGame] = useState<GameFilter>("All");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setError(null);
    setLoaded(false);
    const params = new URLSearchParams({ limit: String(PER_PAGE), page: String(page) });
    if (game !== "All") params.set("game", game);

    fetch(`${API}/api/matches/?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load matches (${r.status})`);
        return r.json() as Promise<MatchResp>;
      })
      .then((d) => {
        setData(d);
        setLoaded(true);
      })
      .catch((e: Error) => setError(e.message));
  }, [game, page]);

  useEffect(() => { setPage(1); }, [game]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PER_PAGE)) : 1;
  const activeColor = GAME_TABS.find((t) => t.label === game)!.color;

  return (
    <main style={s.container}>
      <div className="page-content">
        <h1 style={s.title}>Match history</h1>
        <p style={s.subtitle}>All logged series results</p>

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

        {!loaded && !error && (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {[...Array(6)].map((_, i) => (
              <div key={i} className="skeleton-line" style={{ height: 44, opacity: 1 - i * 0.1 }} />
            ))}
          </div>
        )}

        {loaded && data && data.items.length === 0 && (
          <div style={{ padding: "2.5rem 1rem", textAlign: "center", opacity: 0.5 }}>
            No matches recorded yet.
          </div>
        )}

        {loaded && data && data.items.length > 0 && (
          <section style={{ ...s.card, borderColor: `${activeColor}55` }}>
            <div style={{ ...s.row, ...s.header }}>
              <div style={s.dateCol}>Date</div>
              <div style={s.gameCol}>Game</div>
              <div style={s.matchupCol}>Matchup</div>
              <div style={s.formatCol}>Format</div>
              <div style={s.scoreCol}>Score</div>
              <div style={s.leagueCol}>League</div>
            </div>
            {data.items.map((m) => {
              const isVal = m.game === "Valorant";
              const t1Won = m.winnerTeamId === m.team1Id;
              return (
                <Link key={m._id} href={`/matches/${m._id}`} style={{ textDecoration: "none", color: "inherit" }}>
                  <div className="data-row row-enter" style={{ ...s.row, cursor: "pointer" }}>
                    <div style={{ ...s.dateCol, opacity: 0.7 }}>{formatDate(m.date)}</div>
                    <div style={s.gameCol}>
                      <span style={{
                        padding: "0.2rem 0.5rem",
                        borderRadius: 5,
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        background: isVal ? "rgba(255,70,85,0.15)" : "rgba(200,155,60,0.15)",
                        color: isVal ? "#ff4655" : "#c89b3c",
                      }}>
                        {isVal ? "VAL" : "LoL"}
                      </span>
                    </div>
                    <div style={s.matchupCol}>
                      <span style={{ fontWeight: t1Won ? 700 : 400, color: t1Won ? "#22c55e" : "white" }}>
                        {m.team1Name}
                      </span>
                      <span style={{ opacity: 0.35, margin: "0 0.4rem" }}>vs</span>
                      <span style={{ fontWeight: !t1Won ? 700 : 400, color: !t1Won ? "#22c55e" : "white" }}>
                        {m.team2Name}
                      </span>
                    </div>
                    <div style={{ ...s.formatCol, opacity: 0.6 }}>{m.format ?? "—"}</div>
                    <div style={s.scoreCol} className="tabular-nums">
                      {m.team1Score ?? 0}<span style={{ opacity: 0.3 }}>–</span>{m.team2Score ?? 0}
                    </div>
                    <div style={{ ...s.leagueCol, opacity: 0.55, fontSize: "0.8rem" }}>
                      {m.leagueName ?? "—"}
                    </div>
                  </div>
                </Link>
              );
            })}
          </section>
        )}

        {loaded && data && totalPages > 1 && (
          <div style={s.pagination}>
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              style={s.pageBtn}
            >
              ← Prev
            </button>
            <span className="tabular-nums" style={{ opacity: 0.6 }}>
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              style={s.pageBtn}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </main>
  );
}

export default function MatchesPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" }} />}>
      <MatchesContent />
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
    background: "rgba(255,255,255,0.04)",
    borderRadius: 16,
    overflow: "hidden",
  },
  row: {
    display: "grid",
    gridTemplateColumns: "110px 70px 1.5fr 70px 80px 100px",
    gap: "0.75rem",
    padding: "0.8rem 1rem",
    alignItems: "center",
    borderBottom: "1px solid rgba(255,255,255,0.07)",
    fontSize: "0.9rem",
  },
  header: {
    background: "rgba(255,255,255,0.06)",
    fontWeight: 700,
    fontSize: "0.8rem",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    opacity: 0.8,
  },
  dateCol: {},
  gameCol: {},
  matchupCol: {},
  formatCol: { textAlign: "center" },
  scoreCol: { textAlign: "center", fontWeight: 600 },
  leagueCol: {},
  pagination: { display: "flex", gap: "1rem", alignItems: "center", justifyContent: "center", marginTop: "1.25rem" },
  pageBtn: {
    padding: "0.4rem 1rem",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.15)",
    background: "transparent",
    color: "rgba(255,255,255,0.7)",
    cursor: "pointer",
    fontSize: "0.85rem",
  },
};
