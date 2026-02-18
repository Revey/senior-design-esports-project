"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { CSSProperties } from "react";

function isCSU(input: string): boolean {
  const t = input.trim().toLowerCase();
  return (
    t === "csu" ||
    t === "cleveland state" ||
    t === "cleveland state university" ||
    t === "csu vikes" ||
    t === "cleveland state vikes" ||
    t === "vikes" ||
    t === "csu vikings"
  );
}

export default function ValorantTeamSearchPage() {
  const [team, setTeam] = useState<string>("");
  const router = useRouter();

  function handleContinue(): void {
    if (isCSU(team)) {
      router.push("/valorant/stats?team=CSU");
      return;
    }
    alert('Demo mode: try "CSU" or use autofill.');
  }

  return (
    <main style={styles.container}>
      <h1 style={styles.title}>Valorant Team Search</h1>

      <div style={styles.form}>
        <label htmlFor="team" style={styles.label}>
          College team
        </label>

        <input
          id="team"
          type="text"
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          placeholder='e.g., "CSU"'
          style={styles.input}
          list="team-suggestions-valorant"
          autoComplete="on"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleContinue();
          }}
        />

        <datalist id="team-suggestions-valorant">
          <option value="CSU" />
          <option value="Cleveland State University" />
          <option value="CSU Vikes" />
          <option value="Cleveland State Vikes" />
          <option value="Cleveland State" />
        </datalist>

        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setTeam("Cleveland State University")}
            style={styles.secondaryBtn}
          >
            Autofill: Cleveland State University
          </button>

          <button type="button" onClick={handleContinue} style={styles.primaryBtn}>
            Continue
          </button>

          <button type="button" onClick={() => router.push("/")} style={styles.ghostBtn}>
            Back
          </button>
        </div>
      </div>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0f172a",
    color: "white",
    padding: "2rem",
  },
  title: {
    fontSize: "2.2rem",
    marginBottom: "1.5rem",
    textAlign: "center",
  },
  form: {
    width: "min(520px, 92vw)",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    padding: "1.25rem",
    borderRadius: "16px",
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.06)",
  },
  label: { fontSize: "1rem", opacity: 0.9 },
  input: {
    padding: "0.9rem 1rem",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.2)",
    background: "rgba(0,0,0,0.25)",
    color: "white",
    fontSize: "1.05rem",
    outline: "none",
  },
  primaryBtn: {
    padding: "0.9rem 1rem",
    borderRadius: "12px",
    border: "none",
    cursor: "pointer",
    backgroundColor: "#2563eb",
    color: "white",
    fontSize: "1rem",
  },
  secondaryBtn: {
    padding: "0.9rem 1rem",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.18)",
    cursor: "pointer",
    backgroundColor: "rgba(255,255,255,0.08)",
    color: "white",
    fontSize: "1rem",
  },
  ghostBtn: {
    padding: "0.9rem 1rem",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.18)",
    cursor: "pointer",
    backgroundColor: "transparent",
    color: "white",
    fontSize: "1rem",
    opacity: 0.9,
  },
};
