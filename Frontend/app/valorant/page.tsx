"use client";

import { useRouter } from "next/navigation";
import { useState, useMemo } from "react";
import type { CSSProperties } from "react";
import { filterValTeams, VAL_TEAMS, type ValTeam } from "./valTeamSearchUtils";

// ── Team card ─────────────────────────────────────────────────────────────────

function TeamCard({ team, onClick }: { team: ValTeam; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="val-team-card">
      <span style={styles.teamName}>{team.teamName}</span>
      {team.school && team.school !== team.teamName && (
        <span style={styles.schoolName}>{team.school}</span>
      )}
    </button>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ValorantTeamSearchPage() {
  const [query, setQuery] = useState<string>("");
  const router = useRouter();

  const filtered = useMemo(() => filterValTeams(query), [query]);
  const totalCount = VAL_TEAMS.length;

  function navigateToTeam(slug: string): void {
    router.push(`/valorant/stats?team=${slug}`);
  }

  function handleContinue(): void {
    if (filtered.length === 1) {
      navigateToTeam(filtered[0].slug);
      return;
    }
    if (filtered.length === 0) {
      alert("No matching teams found.");
      return;
    }
    const exact = filtered.find(
      (t) =>
        t.teamName.toLowerCase() === query.trim().toLowerCase() ||
        t.school.toLowerCase() === query.trim().toLowerCase()
    );
    if (exact) {
      navigateToTeam(exact.slug);
    } else {
      alert("Multiple teams match — select one from the list below.");
    }
  }

  return (
    <>
      <style>{`
        .val-team-card {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 0.3rem;
          padding: 0.9rem 1.1rem;
          border-radius: 12px;
          border: 1px solid rgba(255,255,255,0.1);
          background: rgba(255,255,255,0.05);
          color: white;
          cursor: pointer;
          text-align: left;
          transition: background 0.15s, border-color 0.15s, transform 0.1s;
          width: 100%;
          box-sizing: border-box;
        }
        .val-team-card:hover {
          background: rgba(255,70,85,0.2);
          border-color: rgba(255,70,85,0.55);
          transform: translateY(-1px);
        }
      `}</style>

      <main style={styles.container}>
        <h1 style={styles.title}>Valorant</h1>
        <p style={styles.subtitle}>Select a Team</p>

        {/* Search bar */}
        <div style={styles.searchWrapper}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by team or school name…"
            style={styles.input}
            autoComplete="off"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleContinue();
              if (e.key === "Escape") setQuery("");
            }}
            autoFocus
          />
          {query && (
            <button
              type="button"
              style={styles.clearBtn}
              onClick={() => setQuery("")}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        {/* Result count — hidden when full list is showing */}
        <p style={styles.resultCount}>
          {filtered.length === 0
            ? "No teams found"
            : filtered.length === totalCount
            ? ""
            : `${filtered.length} team${filtered.length !== 1 ? "s" : ""} found`}
        </p>

        {/* Team grid */}
        <div style={styles.grid}>
          {filtered.map((team) => (
            <TeamCard
              key={team.slug + team.teamName}
              team={team}
              onClick={() => navigateToTeam(team.slug)}
            />
          ))}
        </div>

        {/* Back */}
        <button type="button" onClick={() => router.push("/")} style={styles.backBtn}>
          ← Back
        </button>
      </main>
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles: Record<string, CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    backgroundColor: "#0f172a",
    color: "white",
    padding: "2.5rem 1.5rem 4rem",
  },
  title: {
    fontSize: "2.2rem",
    fontWeight: 700,
    marginBottom: "0.25rem",
    textAlign: "center",
    letterSpacing: "-0.02em",
  },
  subtitle: {
    fontSize: "0.95rem",
    opacity: 0.5,
    marginBottom: "2rem",
    textAlign: "center",
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },
  searchWrapper: {
    position: "relative",
    width: "min(560px, 92vw)",
    marginBottom: "0.75rem",
  },
  input: {
    width: "100%",
    padding: "0.9rem 2.8rem 0.9rem 1.1rem",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.18)",
    background: "rgba(255,255,255,0.07)",
    color: "white",
    fontSize: "1.05rem",
    outline: "none",
    boxSizing: "border-box",
  },
  clearBtn: {
    position: "absolute",
    right: "0.8rem",
    top: "50%",
    transform: "translateY(-50%)",
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.45)",
    cursor: "pointer",
    fontSize: "0.9rem",
    padding: "0.2rem",
    lineHeight: 1,
  },
  resultCount: {
    fontSize: "0.8rem",
    opacity: 0.4,
    marginBottom: "1.25rem",
    letterSpacing: "0.03em",
    textTransform: "uppercase",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: "0.75rem",
    width: "min(960px, 94vw)",
    marginBottom: "2.5rem",
  },
  teamName: {
    fontSize: "0.95rem",
    fontWeight: 600,
    lineHeight: 1.3,
  },
  schoolName: {
    fontSize: "0.75rem",
    opacity: 0.5,
    lineHeight: 1.3,
  },
  backBtn: {
    padding: "0.6rem 1.2rem",
    borderRadius: "10px",
    border: "1px solid rgba(255,255,255,0.15)",
    background: "transparent",
    color: "rgba(255,255,255,0.6)",
    cursor: "pointer",
    fontSize: "0.9rem",
  },
};