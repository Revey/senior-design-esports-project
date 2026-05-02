"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";

export default function RSOAuthPage() {
  const router = useRouter();
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/valorant/auth/login");
      const data = await res.json();
      if (data.redirect_url) {
        // For demo purposes, simulate success instead of redirecting
        // In production: window.location.href = data.redirect_url;
        setTimeout(() => {
          setConnected(true);
          setLoading(false);
        }, 1500);
      }
    } catch {
      setLoading(false);
    }
  };

  return (
    <main style={styles.container}>
      <div style={styles.content}>
        {/* Header */}
        <div style={styles.headerRow}>
          <h1 style={styles.title}>Riot Sign On</h1>
          <button style={styles.backBtn} onClick={() => router.push("/valorant/stats")}>
            Back to Stats
          </button>
        </div>

        {/* Explanation */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Connect Your Riot Account</h2>
          <p style={styles.text}>
            Linking your Riot account allows CSU Esports Hub to track your CVAL match history
            including custom games. This enables us to display accurate stats for collegiate
            league matches that are not tracked by public APIs.
          </p>
          <ul style={styles.list}>
            <li>We only access match history data</li>
            <li>We never access account credentials or payment information</li>
            <li>You can revoke access at any time via your Riot account settings</li>
          </ul>
        </section>

        {/* Connect Button / Success State */}
        <section style={styles.card}>
          {!connected ? (
            <div style={styles.connectSection}>
              <button
                style={{
                  ...styles.connectBtn,
                  opacity: loading ? 0.7 : 1,
                  cursor: loading ? "not-allowed" : "pointer",
                }}
                onClick={handleConnect}
                disabled={loading}
              >
                {loading ? "Connecting..." : "Connect Your Riot Account"}
              </button>
              <p style={styles.hint}>
                You will be redirected to Riot Games to authorize access.
              </p>
            </div>
          ) : (
            <div style={styles.successSection}>
              <div style={styles.checkmark}>&#10003;</div>
              <h3 style={styles.successTitle}>Account Linked Successfully</h3>
              <p style={styles.successText}>
                Your CVAL stats will sync within 24 hours.
              </p>
            </div>
          )}
        </section>

      </div>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0f172a",
    color: "white",
    padding: "2rem",
  },
  content: {
    maxWidth: "800px",
    margin: "0 auto",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "1rem",
    marginBottom: "1.5rem",
  },
  title: {
    fontSize: "2rem",
    margin: 0,
  },
  backBtn: {
    padding: "0.7rem 1rem",
    borderRadius: 12,
    border: "none",
    cursor: "pointer",
    background: "#2563eb",
    color: "white",
  },
  card: {
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: "1.5rem",
    marginBottom: "1rem",
  },
  sectionTitle: {
    fontSize: "1.3rem",
    marginTop: 0,
    marginBottom: "0.75rem",
    color: "#dc2626",
  },
  text: {
    opacity: 0.9,
    lineHeight: 1.6,
    marginBottom: "0.75rem",
  },
  list: {
    margin: 0,
    paddingLeft: "1.25rem",
    opacity: 0.85,
    lineHeight: 1.8,
  },
  connectSection: {
    textAlign: "center" as const,
    padding: "1rem 0",
  },
  connectBtn: {
    padding: "1rem 2rem",
    fontSize: "1.1rem",
    fontWeight: 700,
    borderRadius: 12,
    border: "none",
    cursor: "pointer",
    background: "#dc2626",
    color: "white",
    transition: "opacity 0.2s",
  },
  hint: {
    marginTop: "0.75rem",
    opacity: 0.6,
    fontSize: "0.9rem",
  },
  successSection: {
    textAlign: "center" as const,
    padding: "1.5rem 0",
  },
  checkmark: {
    width: 60,
    height: 60,
    borderRadius: "50%",
    background: "#16a34a",
    color: "white",
    fontSize: "2rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "0 auto 1rem",
  },
  successTitle: {
    fontSize: "1.3rem",
    margin: 0,
    color: "#16a34a",
  },
  successText: {
    opacity: 0.85,
    marginTop: "0.5rem",
  },
  rosterGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "0.75rem",
    marginTop: "1rem",
  },
  playerCard: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    padding: "0.75rem",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(0,0,0,0.18)",
  },
  playerCheck: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    background: "#16a34a",
    color: "white",
    fontSize: "0.9rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  playerIGN: {
    fontWeight: 600,
  },
  playerMeta: {
    opacity: 0.7,
    fontSize: "0.85rem",
  },
};
