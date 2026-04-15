"use client";

import { useEffect, useState, Suspense } from "react";
import type { CSSProperties } from "react";

type TournamentMatch = {
  round: string;
  team_a: string;
  team_b: string;
  score_a: number | null;
  score_b: number | null;
  status: string;
};

type Tournament = {
  slug: string;
  name: string;
  game: string;
  format: string;
  status: string;
  start_date: string;
  end_date: string;
  teams: string[];
  matches: TournamentMatch[];
};

type StatusFilter = "all" | "upcoming" | "live" | "completed";

const STATUS_TABS: { label: string; value: StatusFilter; color: string }[] = [
  { label: "All", value: "all", color: "#2563eb" },
  { label: "Live", value: "live", color: "#22c55e" },
  { label: "Upcoming", value: "upcoming", color: "#eab308" },
  { label: "Completed", value: "completed", color: "#6b7280" },
];

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

function statusBadgeStyle(status: string): CSSProperties {
  const colors: Record<string, { bg: string; fg: string }> = {
    live: { bg: "rgba(34,197,94,0.15)", fg: "#22c55e" },
    upcoming: { bg: "rgba(234,179,8,0.15)", fg: "#eab308" },
    completed: { bg: "rgba(107,114,128,0.15)", fg: "#9ca3af" },
  };
  const c = colors[status] ?? colors.completed;
  return {
    padding: "0.25rem 0.65rem",
    borderRadius: 6,
    fontSize: "0.8rem",
    fontWeight: 600,
    background: c.bg,
    color: c.fg,
    textTransform: "capitalize" as const,
  };
}

function gameBadgeStyle(game: string): CSSProperties {
  const isVal = game === "Valorant";
  return {
    padding: "0.2rem 0.55rem",
    borderRadius: 5,
    fontSize: "0.75rem",
    fontWeight: 600,
    background: isVal ? "rgba(255,70,85,0.15)" : "rgba(200,155,60,0.15)",
    color: isVal ? "#ff4655" : "#c89b3c",
  };
}

function TournamentsContent() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setError(null);
    setLoaded(false);
    const params = new URLSearchParams();
    if (filter !== "all") params.set("status", filter);

    fetch(`${API}/api/tournaments?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load tournaments (${r.status})`);
        return r.json() as Promise<Tournament[]>;
      })
      .then((data) => {
        setTournaments(data);
        setLoaded(true);
      })
      .catch((e: Error) => setError(e.message));
  }, [filter]);

  function toggle(slug: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  const activeColor = STATUS_TABS.find((t) => t.value === filter)!.color;

  return (
    <main style={s.container}>
      <div className="page-content">
      <h1 style={s.title}>Tournaments</h1>
      <p style={s.subtitle}>Collegiate esports brackets and results</p>

      {/* Status filter */}
      <div style={s.tabRow}>
        {STATUS_TABS.map((tab) => {
          const active = filter === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
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
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton-line" style={{ height: "140px", opacity: 1 - i * 0.2 }} />
          ))}
        </div>
      )}

      {loaded && tournaments.length === 0 && !error && (
        <div style={{ padding: "2.5rem 1rem", textAlign: "center", opacity: 0.5 }}>
          No tournaments match this filter.
        </div>
      )}

      {/* Tournament cards */}
      <div style={s.grid}>
        {tournaments.map((t) => {
          const isOpen = expanded.has(t.slug);
          return (
            <section
              key={t.slug}
              style={{ ...s.card, borderColor: `${activeColor}33` }}
            >
              {/* Header */}
              <div style={s.cardHeader}>
                <div>
                  <h3 style={s.tournName}>{t.name}</h3>
                  <div style={s.metaRow}>
                    <span style={gameBadgeStyle(t.game)}>{t.game === "Valorant" ? "VAL" : "LoL"}</span>
                    <span style={statusBadgeStyle(t.status)}>{t.status}</span>
                    <span style={s.format}>{t.format}</span>
                  </div>
                </div>
                <div style={s.dateBlock}>
                  <div style={s.dateLabel}>
                    {t.start_date} &mdash; {t.end_date}
                  </div>
                  <div style={s.teamCount}>{t.teams.length} teams</div>
                </div>
              </div>

              {/* Teams list */}
              <div style={s.teamsList}>
                {t.teams.map((name) => (
                  <span key={name} style={s.teamChip}>{name}</span>
                ))}
              </div>

              {/* Matches toggle */}
              <button onClick={() => toggle(t.slug)} style={s.toggleBtn}>
                {isOpen ? "Hide Matches \u25B2" : `Show Matches (${t.matches.length}) \u25BC`}
              </button>

              {/* Matches */}
              {isOpen && (
                <div style={s.matchesSection}>
                  {t.matches.map((m, idx) => (
                    <div key={idx} className="data-row" style={s.matchRow}>
                      <div style={s.roundLabel}>{m.round}</div>
                      <div style={s.matchTeams}>
                        <span
                          style={{
                            fontWeight: m.score_a != null && m.score_b != null && m.score_a > m.score_b ? 700 : 400,
                            color: m.score_a != null && m.score_b != null && m.score_a > m.score_b ? "#22c55e" : "inherit",
                          }}
                        >
                          {m.team_a}
                        </span>
                        <span style={s.vs}>
                          {m.score_a != null && m.score_b != null
                            ? `${m.score_a} - ${m.score_b}`
                            : "vs"}
                        </span>
                        <span
                          style={{
                            fontWeight: m.score_a != null && m.score_b != null && m.score_b > m.score_a ? 700 : 400,
                            color: m.score_a != null && m.score_b != null && m.score_b > m.score_a ? "#22c55e" : "inherit",
                          }}
                        >
                          {m.team_b}
                        </span>
                      </div>
                      <span style={statusBadgeStyle(m.status)}>{m.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
      </div>
    </main>
  );
}

export default function TournamentsPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100dvh", backgroundColor: "#0d1526", color: "white", padding: "2rem" }} />}>
      <TournamentsContent />
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

  grid: { display: "flex", flexDirection: "column" as const, gap: "1rem" },

  card: {
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: "1.25rem",
  },

  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "1rem",
    flexWrap: "wrap" as const,
  },
  tournName: { fontSize: "1.25rem", margin: 0 },
  metaRow: { display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.5rem", flexWrap: "wrap" as const },
  format: { fontSize: "0.85rem", opacity: 0.65 },

  dateBlock: { textAlign: "right" as const },
  dateLabel: { fontSize: "0.9rem", opacity: 0.7 },
  teamCount: { fontSize: "0.85rem", opacity: 0.5, marginTop: "0.2rem" },

  teamsList: {
    display: "flex",
    gap: "0.4rem",
    flexWrap: "wrap" as const,
    marginTop: "0.75rem",
  },
  teamChip: {
    padding: "0.3rem 0.65rem",
    borderRadius: 7,
    fontSize: "0.8rem",
    background: "rgba(255,255,255,0.08)",
    border: "1px solid rgba(255,255,255,0.1)",
  },

  toggleBtn: {
    marginTop: "0.75rem",
    padding: "0.45rem 1rem",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.15)",
    background: "transparent",
    color: "rgba(255,255,255,0.6)",
    cursor: "pointer",
    fontSize: "0.85rem",
    fontWeight: 500,
    transition: "color 0.15s",
  },

  matchesSection: {
    marginTop: "0.75rem",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.4rem",
  },
  matchRow: {
    display: "grid",
    gridTemplateColumns: "140px 1fr 100px",
    gap: "0.75rem",
    padding: "0.65rem 0.75rem",
    borderRadius: 10,
    background: "rgba(0,0,0,0.2)",
    border: "1px solid rgba(255,255,255,0.06)",
    alignItems: "center",
  },
  roundLabel: { fontSize: "0.85rem", fontWeight: 600, opacity: 0.8 },
  matchTeams: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    fontSize: "0.9rem",
  },
  vs: {
    opacity: 0.5,
    fontWeight: 700,
    fontSize: "0.8rem",
    minWidth: 40,
    textAlign: "center" as const,
  },
};
