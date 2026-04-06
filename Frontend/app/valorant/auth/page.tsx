"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { CSSProperties } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const CSU_ROSTER = [
  { ign: "VIKES Lian",        name: "Lian",              role: "Smokes" },
  { ign: "VIKES N0ths",       name: "Ashton Langenek",   role: "Controller" },
  { ign: "VIKES Kamino",      name: "Connor Maluk",      role: "Controller" },
  { ign: "VIKES wyyu",        name: "Eric Weatherall",   role: "Duelist" },
  { ign: "VIKES Exquisitely", name: "Ziyeir Norman",     role: "Sentinel" },
];

interface LinkedPlayer {
  puuid: string;
  gameName: string;
  tagLine: string;
}

interface AuthStatus {
  authenticated: boolean;
  puuid?: string;
  gameName?: string;
  tagLine?: string;
}

export default function RSOAuthPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [authStatus, setAuthStatus] = useState<AuthStatus>({ authenticated: false });
  const [linkedPlayers, setLinkedPlayers] = useState<LinkedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [callbackStatus, setCallbackStatus] = useState<"success" | "error" | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  // Check URL params from OAuth callback redirect
  useEffect(() => {
    const status = searchParams.get("status");
    if (status === "success") {
      setCallbackStatus("success");
    } else if (status === "error") {
      setCallbackStatus("error");
      setErrorMessage(searchParams.get("message") || "Authentication failed");
    }
  }, [searchParams]);

  // Check auth status and fetch linked players
  useEffect(() => {
    async function checkStatus() {
      try {
        const [statusRes, playersRes] = await Promise.all([
          fetch(`${BACKEND_URL}/api/valorant/auth/status`, { credentials: "include" }),
          fetch(`${BACKEND_URL}/api/valorant/auth/linked-players`),
        ]);
        if (statusRes.ok) {
          const data = await statusRes.json();
          setAuthStatus(data);
        }
        if (playersRes.ok) {
          const data = await playersRes.json();
          setLinkedPlayers(data.players || []);
        }
      } catch {
        // Backend may not be running — that's ok for dev
      } finally {
        setLoading(false);
      }
    }
    checkStatus();
  }, [callbackStatus]);

  const handleConnect = () => {
    // Full page redirect to backend, which 302s to Riot
    window.location.href = `${BACKEND_URL}/api/valorant/auth/login`;
  };

  const handleLogout = () => {
    // Full page redirect to backend logout
    window.location.href = `${BACKEND_URL}/api/valorant/auth/logout`;
  };

  const isPlayerLinked = (ign: string) => {
    return linkedPlayers.some(
      (lp) => ign.toLowerCase().includes(lp.gameName.toLowerCase())
    );
  };

  const isAuthenticated = authStatus.authenticated || callbackStatus === "success";

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

        {/* Callback status banner */}
        {callbackStatus === "success" && (
          <div style={styles.successBanner}>
            Riot account linked successfully!
          </div>
        )}
        {callbackStatus === "error" && (
          <div style={styles.errorBanner}>
            Authentication failed: {errorMessage}
          </div>
        )}

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
          <p style={{ ...styles.text, marginTop: "0.75rem", opacity: 0.7, fontSize: "0.9rem" }}>
            See our <a href="/privacy" style={{ color: "#60a5fa" }}>Privacy Policy</a> for full details.
          </p>
        </section>

        {/* Connect / Status Section */}
        <section style={styles.card}>
          {loading ? (
            <div style={styles.connectSection}>
              <p style={styles.hint}>Checking authentication status...</p>
            </div>
          ) : isAuthenticated ? (
            <div style={styles.successSection}>
              <div style={styles.checkmark}>&#10003;</div>
              <h3 style={styles.successTitle}>Account Linked</h3>
              {authStatus.gameName && (
                <p style={styles.successText}>
                  Signed in as <strong>{authStatus.gameName}#{authStatus.tagLine}</strong>
                </p>
              )}
              <p style={styles.successText}>
                Your CVAL stats will sync within 24 hours.
              </p>
              <button style={styles.logoutBtn} onClick={handleLogout}>
                Disconnect Account
              </button>
            </div>
          ) : (
            <div style={styles.connectSection}>
              <button style={styles.connectBtn} onClick={handleConnect}>
                Sign in with Riot Games
              </button>
              <p style={styles.hint}>
                You will be redirected to Riot Games to authorize access.
              </p>
            </div>
          )}
        </section>

        {/* Connected Players */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Connected Players</h2>
          <p style={styles.text}>
            CSU roster players with linked Riot accounts:
          </p>
          <div style={styles.rosterGrid}>
            {CSU_ROSTER.map((player) => {
              const linked = isPlayerLinked(player.ign);
              return (
                <div key={player.ign} style={styles.playerCard}>
                  <div style={{
                    ...styles.playerCheck,
                    background: linked ? "#16a34a" : "rgba(255,255,255,0.1)",
                    color: linked ? "white" : "rgba(255,255,255,0.3)",
                  }}>
                    {linked ? "\u2713" : "?"}
                  </div>
                  <div>
                    <div style={styles.playerIGN}>{player.ign}</div>
                    <div style={styles.playerMeta}>
                      {player.role} {linked ? "" : "- Not connected"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
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
  successBanner: {
    padding: "1rem",
    borderRadius: 12,
    background: "rgba(22, 163, 74, 0.2)",
    border: "1px solid rgba(22, 163, 74, 0.4)",
    color: "#4ade80",
    fontWeight: 600,
    textAlign: "center" as const,
    marginBottom: "1rem",
  },
  errorBanner: {
    padding: "1rem",
    borderRadius: 12,
    background: "rgba(220, 38, 38, 0.2)",
    border: "1px solid rgba(220, 38, 38, 0.4)",
    color: "#f87171",
    fontWeight: 600,
    textAlign: "center" as const,
    marginBottom: "1rem",
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
  logoutBtn: {
    marginTop: "1rem",
    padding: "0.6rem 1.2rem",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.2)",
    cursor: "pointer",
    background: "transparent",
    color: "rgba(255,255,255,0.7)",
    fontSize: "0.9rem",
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
