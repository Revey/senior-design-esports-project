"use client";

import { useEffect, useState } from "react";

type HealthStatus = "ok" | "degraded" | "down" | "checking";

const API = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

export default function Footer() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const r = await fetch(`${API}/api/health`, { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const data = (await r.json()) as { status?: string };
        if (cancelled) return;
        setStatus(data.status === "ok" ? "ok" : "degraded");
      } catch {
        if (!cancelled) setStatus("down");
      }
    }
    check();
    const id = setInterval(check, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const pill =
    status === "ok"
      ? { bg: "rgba(34,197,94,0.15)", fg: "#22c55e", label: "API online" }
      : status === "degraded"
      ? { bg: "rgba(234,179,8,0.15)", fg: "#eab308", label: "API degraded" }
      : status === "down"
      ? { bg: "rgba(239,68,68,0.15)", fg: "#ef4444", label: "API offline" }
      : { bg: "rgba(255,255,255,0.08)", fg: "rgba(255,255,255,0.5)", label: "Checking…" };

  return (
    <footer style={{
      width: "100%",
      padding: "1.5rem 2rem",
      backgroundColor: "#0a0f1e",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      textAlign: "center",
      color: "rgba(255,255,255,0.35)",
      fontSize: "0.75rem",
      lineHeight: 1.6,
    }}>
      <p>
        Campus Rankers is not affiliated with or sponsored by Riot Games, Inc. or VALORANT Esports.
        VALORANT and League of Legends are trademarks of Riot Games, Inc.
      </p>
      <p style={{ marginTop: "0.25rem", display: "flex", gap: "0.75rem", justifyContent: "center", alignItems: "center", flexWrap: "wrap" }}>
        <a href="/privacy" style={{ color: "rgba(255,255,255,0.5)", textDecoration: "underline" }}>
          Privacy Policy
        </a>
        <span
          title={`Backend: ${status}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
            padding: "0.15rem 0.55rem",
            borderRadius: 999,
            background: pill.bg,
            color: pill.fg,
            fontSize: "0.7rem",
            fontWeight: 600,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: pill.fg, display: "inline-block" }} />
          {pill.label}
        </span>
      </p>
    </footer>
  );
}
