"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";

export default function Home() {
  const router = useRouter();

  return (
    <main style={styles.container}>
      <h1 style={styles.title}>Choose Your Game</h1>

      <div style={styles.grid}>
        {/* Valorant */}
        <button
          data-card
          type="button"
          style={styles.card}
          aria-label="Select Valorant"
          onClick={() => router.push("/valorant")}
        >
          <div style={styles.imageWrap}>
            <Image
              src="/images/valorantimage.png"
              alt="Valorant"
              fill
              sizes="(max-width: 768px) 320px, 360px"
              style={{ objectFit: "contain" }}
              priority
            />
          </div>
        </button>

        {/* League of Legends */}
        <button
          data-card
          type="button"
          style={styles.card}
          aria-label="Select League of Legends"
          onClick={() => router.push("/league")}
        >
          <div style={styles.imageWrap}>
            <Image
              src="/images/league-of-legends.png"
              alt="League of Legends"
              fill
              sizes="(max-width: 768px) 320px, 360px"
              style={{ objectFit: "contain" }}
            />
          </div>
        </button>
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
    fontSize: "2.5rem",
    marginBottom: "2rem",
    textAlign: "center",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(260px, 360px))",
    gap: "2rem",
  },
  card: {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.15)",
    borderRadius: "16px",
    padding: "14px",
    cursor: "pointer",
    width: "100%",
    display: "block",
  },
  imageWrap: {
    position: "relative",
    width: "100%",
    height: "360px",
  },
};
