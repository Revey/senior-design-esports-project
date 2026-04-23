"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { CSSProperties } from "react";

const API_BASE_URL = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

type RankInfo = {
  tier_text: string | null;
  lp: number | null;
  wins: number | null;
  losses: number | null;
  win_rate: number | null;
} | null;

type RoleInfo = {
  role: string;
  percentage: number;
};

type MasteryInfo = {
  champion: string;
  champion_id: number | null;
  mastery_level: number | null;
  mastery_points: number | null;
};

type Player = {
  _id?: string;
  team_name: string | null;
  school: string | null;
  display_name: string | null;
  team_role_from_clol: string | null;
  riot_id: string | null;
  game_name: string | null;
  tag_line: string | null;
  puuid: string | null;
  updated_at_utc: string | null;
  scrape_status: string | null;
  source: string | null;
  opgg_url: string | null;
  summoner_name: string | null;
  ladder_rank: number | null;
  error?: string | null;
  solo_duo_rank: RankInfo;
  highest_rank: {
    tier_text: string | null;
    lp: number | null;
  } | null;
  flex_rank: RankInfo;
  top_roles: RoleInfo[];
  main_role: string | null;
  top_5_masteries: MasteryInfo[];
};

type ApiResponse = {
  ok: boolean;
  team: string;
  count: number;
  players: Player[];
  error?: string;
};

function safeText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not found";
  return String(value);
}

function formatRank(rank: RankInfo): string {
  if (!rank || !rank.tier_text) return "Not found";

  const pieces: string[] = [rank.tier_text];

  if (rank.lp !== null && rank.lp !== undefined) {
    pieces.push(`${rank.lp} LP`);
  }

  if (
    rank.wins !== null &&
    rank.wins !== undefined &&
    rank.losses !== null &&
    rank.losses !== undefined
  ) {
    pieces.push(`${rank.wins}W-${rank.losses}L`);
  }

  if (rank.win_rate !== null && rank.win_rate !== undefined) {
    pieces.push(`${rank.win_rate}% WR`);
  }

  return pieces.join(" • ");
}

function formatHighestRank(
  rank: { tier_text: string | null; lp: number | null } | null
): string {
  if (!rank || !rank.tier_text) return "Not found";
  if (rank.lp === null || rank.lp === undefined) return rank.tier_text;
  return `${rank.tier_text} • ${rank.lp} LP`;
}

function TeamInfoRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div style={styles.infoRow}>
      <span style={styles.infoLabel}>{label}</span>
      <span style={styles.infoValue}>{value}</span>
    </div>
  );
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return "Not found";

  try {
    const date = new Date(timestamp);

    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: "UTC",
    }).format(date) + " UTC";
  } catch {
    return "Not found";
  }
}

function PlayerCard({ player }: { player: Player }) {
  return (
    <article style={styles.card}>
      <div style={styles.cardHeader}>
        <div>
          <h2 style={styles.playerName}>{safeText(player.display_name)}</h2>
          <p style={styles.subtleText}>
            Updated: {formatTimestamp(player.updated_at_utc)}
          </p>
        </div>
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Basic Info</h3>
        <TeamInfoRow label="Main Role" value={safeText(player.main_role)} />
        <TeamInfoRow label="Ladder Rank" value={safeText(player.ladder_rank)} />
        <TeamInfoRow
          label="OP.GG"
          value={
            player.opgg_url ? (
              <a href={player.opgg_url} target="_blank" rel="noreferrer" style={styles.link}>
                Open profile
              </a>
            ) : (
              "Not found"
            )
          }
        />
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Ranked</h3>
        <TeamInfoRow label="Solo/Duo" value={formatRank(player.solo_duo_rank)} />
        <TeamInfoRow label="Highest Rank" value={formatHighestRank(player.highest_rank)} />
        <TeamInfoRow label="Flex Rank" value={formatRank(player.flex_rank)} />
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Top Roles</h3>
        {player.top_roles && player.top_roles.length > 0 ? (
          <div style={styles.tagWrap}>
            {player.top_roles.map((role, idx) => (
              <span key={`${role.role}-${idx}`} style={styles.tag}>
                {role.role} {role.percentage}%
              </span>
            ))}
          </div>
        ) : (
          <p style={styles.emptyText}>No role data found.</p>
        )}
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Top 5 Masteries</h3>
        {player.top_5_masteries && player.top_5_masteries.length > 0 ? (
          <div style={styles.masteryList}>
            {player.top_5_masteries.map((champ, idx) => (
              <div key={`${champ.champion}-${idx}`} style={styles.masteryItem}>
                <div style={styles.masteryChampion}>{safeText(champ.champion)}</div>
                <div style={styles.masteryMeta}>
                  Level {safeText(champ.mastery_level)} • {safeText(champ.mastery_points)} pts
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={styles.emptyText}>No mastery data found.</p>
        )}
      </div>

      {player.error && (
        <div style={styles.errorBox}>
          <strong>Scrape Error:</strong> {player.error}
        </div>
      )}
    </article>
  );
}

function LeagueStatsInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const team = useMemo(() => {
    const raw = searchParams.get("team");
    return raw ? decodeURIComponent(raw) : "";
  }, [searchParams]);

  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    async function loadPlayers() {
      if (!team) {
        setError("No team was selected.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");

        const res = await fetch(
          `${API_BASE_URL}/api/league/team-players?team=${encodeURIComponent(team)}`,
          { cache: "no-store" }
        );

        const json: ApiResponse = await res.json();

        if (!res.ok || !json.ok) {
          throw new Error(json.error || "Failed to load team players.");
        }

        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error.");
      } finally {
        setLoading(false);
      }
    }

    loadPlayers();
  }, [team]);

  return (
    <main style={styles.page}>
      <div style={styles.pageInner}>
        <div style={styles.topBar}>
          <button type="button" onClick={() => router.push("/league")} style={styles.backBtn}>
            ← Back
          </button>
        </div>

        <header style={styles.hero}>
          <h1 style={styles.title}>{team || "Team Stats"}</h1>
          <p style={styles.kicker}>League Of Legends Team Details</p>
        </header>

        {loading && <div style={styles.messageBox}>Loading players...</div>}

        {!loading && error && <div style={styles.errorBoxLarge}>{error}</div>}

        {!loading && !error && data && (
          <>
            <div style={styles.summaryBar}>
              <span>
                <strong>Team:</strong> {data.team}
              </span>
              <span>
                <strong>Players Found:</strong> {data.count}
              </span>
            </div>

            {data.players.length === 0 ? (
              <div style={styles.messageBox}>No players were found for this team.</div>
            ) : (
              <div style={styles.grid}>
                {data.players.map((player, idx) => (
                  <PlayerCard key={`${player.riot_id ?? player.display_name ?? "player"}-${idx}`} player={player} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}

export default function LeagueStatsPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100vh", backgroundColor: "#0f172a", color: "white", padding: "2rem" }}>Loading...</main>}>
      <LeagueStatsInner />
    </Suspense>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    backgroundColor: "#0f172a",
    color: "white",
    padding: "2rem 1.25rem 4rem",
  },
  pageInner: {
    width: "min(1300px, 100%)",
    margin: "0 auto",
  },
  topBar: {
    marginBottom: "1rem",
  },
  hero: {
    marginBottom: "1.5rem",
  },
  kicker: {
    fontSize: "0.8rem",
    opacity: 0.65,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    marginBottom: "0.4rem",
  },
  title: {
    fontSize: "2.2rem",
    fontWeight: 700,
    margin: 0,
  },
  subtitle: {
    marginTop: "0.5rem",
    color: "rgba(255,255,255,0.7)",
  },
  summaryBar: {
    display: "flex",
    gap: "1rem",
    flexWrap: "wrap",
    marginBottom: "1.25rem",
    padding: "0.9rem 1rem",
    borderRadius: "14px",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
    gap: "1rem",
  },
  card: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: "16px",
    padding: "1rem",
    boxSizing: "border-box",
  },
  cardHeader: {
    display: "block",
    marginBottom: "1rem",
  },
  playerName: {
    margin: 0,
    fontSize: "1.2rem",
    fontWeight: 700,
  },
  subtleText: {
    margin: "0.35rem 0 0",
    color: "rgba(255,255,255,0.6)",
    fontSize: "0.9rem",
    lineHeight: 1.4,
    wordBreak: "break-word",
  },
  section: {
    marginTop: "1rem",
  },
  sectionTitle: {
    fontSize: "0.95rem",
    marginBottom: "0.65rem",
    color: "#93c5fd",
  },
  infoRow: {
    display: "flex",
    justifyContent: "space-between",
    gap: "1rem",
    padding: "0.45rem 0",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  infoLabel: {
    color: "rgba(255,255,255,0.62)",
    minWidth: "120px",
  },
  infoValue: {
    textAlign: "right",
    wordBreak: "break-word",
  },
  tagWrap: {
    display: "flex",
    gap: "0.5rem",
    flexWrap: "wrap",
  },
  tag: {
    padding: "0.45rem 0.65rem",
    borderRadius: "999px",
    background: "rgba(37,99,235,0.2)",
    border: "1px solid rgba(37,99,235,0.45)",
    fontSize: "0.85rem",
  },
  masteryList: {
    display: "grid",
    gap: "0.55rem",
  },
  masteryItem: {
    padding: "0.7rem 0.8rem",
    borderRadius: "12px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
  },
  masteryChampion: {
    fontWeight: 600,
    marginBottom: "0.2rem",
  },
  masteryMeta: {
    color: "rgba(255,255,255,0.68)",
    fontSize: "0.9rem",
  },
  emptyText: {
    color: "rgba(255,255,255,0.58)",
    margin: 0,
  },
  messageBox: {
    padding: "1rem",
    borderRadius: "14px",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
  },
  errorBox: {
    marginTop: "1rem",
    padding: "0.8rem",
    borderRadius: "12px",
    background: "rgba(239,68,68,0.16)",
    border: "1px solid rgba(239,68,68,0.35)",
    color: "#fecaca",
  },
  errorBoxLarge: {
    padding: "1rem",
    borderRadius: "14px",
    background: "rgba(239,68,68,0.16)",
    border: "1px solid rgba(239,68,68,0.35)",
    color: "#fecaca",
  },
  backBtn: {
    padding: "0.7rem 1rem",
    borderRadius: "10px",
    border: "1px solid rgba(255,255,255,0.14)",
    background: "transparent",
    color: "white",
    cursor: "pointer",
  },
  link: {
    color: "#93c5fd",
    textDecoration: "none",
  },
  mono: {
    fontFamily: "monospace",
    fontSize: "0.82rem",
  },
};