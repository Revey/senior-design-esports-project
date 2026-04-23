"use client";

import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";

type Player = {
  slug: string;
  displayName: string;
  riotId: string;
  role: string | null;
  game: string;
  team_name: string;
  team_slug: string;
  active: boolean;
};

type GameFilter = "All" | "Valorant" | "League of Legends";

const GAME_TABS: { label: GameFilter; color: string }[] = [
  { label: "All", color: "#2563eb" },
  { label: "Valorant", color: "#ff4655" },
  { label: "League of Legends", color: "#c89b3c" },
];

const VAL_ROLES = ["All", "Duelist", "Initiator", "Controller", "Sentinel", "Flex"];
const LOL_ROLES = ["All", "Top", "Jungle", "Mid", "ADC", "Support"];

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

function PlayersContent() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [game, setGame] = useState<GameFilter>("All");
  const [role, setRole] = useState("All");
  const [search, setSearch] = useState("");

  const roles = game === "League of Legends" ? LOL_ROLES : game === "Valorant" ? VAL_ROLES : [];
  const activeColor = GAME_TABS.find((t) => t.label === game)!.color;

  useEffect(() => {
    setError(null);
    setLoaded(false);
    const params = new URLSearchParams({ limit: "200" });
    if (game !== "All") params.set("game", game);
    if (role !== "All") params.set("role", role);

    fetch(`${API}/api/players?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load players (${r.status})`);
        return r.json() as Promise<Player[]>;
      })
      .then((data) => {
        setPlayers(data);
        setLoaded(true);
      })
      .catch((e: Error) => setError(e.message));
  }, [game, role]);

  useEffect(() => { setRole("All"); }, [game]);

  const needle = search.toLowerCase();
  const filteredPlayers = needle
    ? players.filter(
        (p) =>
          p.displayName.toLowerCase().includes(needle) ||
          (p.riotId ?? "").toLowerCase().includes(needle) ||
          (p.team_name ?? "").toLowerCase().includes(needle)
      )
    : players;

  return (
    <main style={s.container}>
      <div className="page-content">
        <h1 style={s.title}>Player rankings</h1>
        <p style={s.subtitle}>Top collegiate esports players</p>

        {/* Game tabs */}
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

        {/* Role filter */}
        {roles.length > 0 && (
          <div style={{ ...s.tabRow, gap: "0.4rem" }}>
            {roles.map((r) => (
              <button
                key={r}
                onClick={() => setRole(r)}
                style={{
                  ...s.roleBtn,
                  background: role === r ? "rgba(255,255,255,0.15)" : "transparent",
                  color: role === r ? "white" : "rgba(255,255,255,0.45)",
                  borderColor: role === r ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.1)",
                }}
              >
                {r}
              </button>
            ))}
          </div>
        )}

        {/* Search */}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search player or Riot ID…"
          style={s.searchInput}
        />

        {error && <p style={{ color: "#f87171" }}>{error}</p>}

        {/* Player table */}
        <section style={{ ...s.card, borderColor: `${activeColor}55` }}>
          <div style={{ ...s.row, ...s.header }}>
            <div style={s.rankCol}>#</div>
            <div style={s.nameCol}>Player</div>
            <div style={s.riotCol}>Riot ID</div>
            <div style={s.teamCol}>Team</div>
            <div style={s.roleCol}>Role</div>
            <div style={s.gameCol}>Game</div>
          </div>

          {!loaded && !error && (
            <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {[...Array(8)].map((_, i) => (
                <div key={i} className="skeleton-line" style={{ height: "40px", opacity: 1 - i * 0.08 }} />
              ))}
            </div>
          )}

          {loaded && filteredPlayers.length === 0 && !error && (
            <div style={{ padding: "2.5rem 1rem", textAlign: "center", opacity: 0.5 }}>
              {search ? "No players match your search." : "No players match these filters."}
            </div>
          )}

          {filteredPlayers.map((p, i) => {
            const isVal = p.game !== "League of Legends";
            return (
              <div
                key={p.slug}
                className="data-row row-enter"
                style={{ ...s.row, animationDelay: `${i * 0.025}s` }}
              >
                <div style={s.rankCol}>
                  <span style={{ ...s.rankBadge, background: i < 3 ? activeColor : "rgba(255,255,255,0.08)" }}>
                    {i + 1}
                  </span>
                </div>

                <div style={s.nameCol}>
                  <Link
                    href={`/players/${p.slug}`}
                    style={{ fontWeight: 600, color: "white", textDecoration: "none" }}
                    className="player-link"
                  >
                    {p.displayName}
                  </Link>
                </div>

                <div style={{ ...s.riotCol, opacity: 0.65, fontSize: "0.82rem" }}>
                  {p.riotId ?? "—"}
                </div>

                <div style={{ ...s.teamCol, opacity: 0.8 }}>
                  {p.team_name || "—"}
                </div>

                <div style={s.roleCol}>
                  {p.role || "—"}
                </div>

                <div style={s.gameCol}>
                  <span
                    style={{
                      ...s.gameBadge,
                      background: isVal ? "rgba(255,70,85,0.15)" : "rgba(200,155,60,0.15)",
                      color: isVal ? "#ff4655" : "#c89b3c",
                    }}
                  >
                    {isVal ? "VAL" : "LoL"}
                  </span>
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </main>
  );
}

export default function PlayersPage() {
  return (
    <Suspense
      fallback={
        <main style={{ minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" }} />
      }
    >
      <PlayersContent />
    </Suspense>
  );
}

const s: Record<string, CSSProperties> = {
  container: { minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" },
  title: { fontSize: "clamp(1.6rem, 3vw, 2.2rem)", fontWeight: 700, letterSpacing: "-0.02em", margin: 0 },
  subtitle: { marginTop: "0.35rem", opacity: 0.55, marginBottom: "1.5rem", fontSize: "0.95rem" },

  searchInput: {
    width: "100%",
    maxWidth: 360,
    padding: "0.55rem 0.9rem",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.05)",
    color: "white",
    fontSize: "0.9rem",
    marginBottom: "1rem",
    outline: "none",
  },
  tabRow: { display: "flex", gap: "0.6rem", marginBottom: "1rem", flexWrap: "wrap" },
  tabBtn: {
    padding: "0.55rem 1.5rem",
    borderRadius: 10,
    border: "1px solid",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: "0.95rem",
    transition: "background 0.15s, color 0.15s, box-shadow 0.15s",
  },
  roleBtn: {
    padding: "0.4rem 1rem",
    borderRadius: 8,
    border: "1px solid",
    cursor: "pointer",
    fontWeight: 500,
    fontSize: "0.85rem",
    transition: "all 0.15s",
  },
  card: {
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.04)",
    borderRadius: 16,
    overflow: "hidden",
  },
  row: {
    display: "grid",
    gridTemplateColumns: "50px 1.4fr 1.6fr 1.2fr 100px 70px",
    gap: "0.5rem",
    padding: "0.75rem 1rem",
    alignItems: "center",
    borderBottom: "1px solid rgba(255,255,255,0.07)",
  },
  header: {
    background: "rgba(255,255,255,0.06)",
    fontWeight: 700,
    fontSize: "0.8rem",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    opacity: 0.8,
  },
  rankCol: { textAlign: "center" as const },
  rankBadge: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 28,
    height: 28,
    borderRadius: 7,
    fontWeight: 700,
    fontSize: "0.85rem",
  },
  nameCol: { display: "flex", alignItems: "center" },
  riotCol: { fontSize: "0.9rem" },
  teamCol: { fontSize: "0.9rem" },
  roleCol: { fontSize: "0.9rem", opacity: 0.85 },
  gameCol: { textAlign: "center" as const },
  gameBadge: {
    padding: "0.15rem 0.45rem",
    borderRadius: 5,
    fontSize: "0.7rem",
    fontWeight: 600,
  },
};