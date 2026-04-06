export default function Footer() {
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
        CSU Esports Hub is not affiliated with or sponsored by Riot Games, Inc. or VALORANT Esports.
        VALORANT and League of Legends are trademarks of Riot Games, Inc.
      </p>
      <p style={{ marginTop: "0.25rem" }}>
        Cleveland State University Esports - Washkewicz College of Engineering
      </p>
      <p style={{ marginTop: "0.25rem" }}>
        <a href="/privacy" style={{ color: "rgba(255,255,255,0.5)", textDecoration: "underline" }}>
          Privacy Policy
        </a>
      </p>
    </footer>
  );
}
