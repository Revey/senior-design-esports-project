import type { CSSProperties } from "react";

const CSU_VALORANT_ROSTER = [
  { ign: "N0ths",       name: "Ashton Langenek",  role: "Controller", major: "Information Systems" },
  { ign: "Kamino",      name: "Connor Maluk",     role: "Controller", major: "Social Studies Education" },
  { ign: "wyyu",        name: "Eric Weatherall",  role: "Duelist",    major: "Business Sports Mgmt" },
  { ign: "Revey",       name: "Daniel Torres",    role: "Duelist",    major: "Computer Science" },
  { ign: "Exquisitely", name: "Ziyeir Norman",    role: "Sentinel",   major: "Chemical Engineering" },
];

export default function AboutPage() {
  return (
    <main style={styles.container}>
      <div style={styles.content}>
        {/* Hero */}
        <section style={styles.hero}>
          <h1 style={styles.heroTitle}>CSU Esports Hub</h1>
          <p style={styles.heroSubtitle}>
            The official data portal for Cleveland State University competitive esports
          </p>
        </section>

        {/* Mission */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Our Mission</h2>
          <p style={styles.text}>
            CSU Esports Hub tracks Cleveland State University student-athletes competing in
            <strong> College VALORANT (CVAL)</strong> and <strong>College League of Legends (CLOL)</strong>.
            Built in partnership with the Washkewicz College of Engineering, this platform provides
            comprehensive performance analytics for our competitive teams.
          </p>
          <p style={styles.text}>
            Many of our players are STEM students who balance rigorous academic programs with
            competitive gaming. This hub celebrates their achievements and provides transparent
            statistics for fans, recruiters, and the esports community.
          </p>
        </section>

        {/* How RSO Works */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>How Riot Sign On Works</h2>
          <p style={styles.text}>
            To access custom game match history (essential for collegiate league tracking), players
            authenticate via Riot Sign On (RSO). Here's how it works:
          </p>
          <ol style={styles.orderedList}>
            <li>
              <strong>Connect Account</strong> - Player clicks "Connect Riot Account" on the stats page
            </li>
            <li>
              <strong>Authenticate</strong> - Player is redirected to Riot Games to authorize access
            </li>
            <li>
              <strong>Permission Granted</strong> - Hub receives permission to read match history including custom games
            </li>
            <li>
              <strong>Stats Sync</strong> - CVAL and CLOL match data syncs automatically within 24 hours
            </li>
          </ol>
          <div style={styles.privacyNote}>
            <strong>Privacy Note:</strong> We only access match history data. We never access account
            credentials, payment information, or personal data beyond what is needed for stats display.
          </div>
        </section>

        {/* Leagues */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Leagues We Track</h2>
          <div style={styles.leagueGrid}>
            <div style={{ ...styles.leagueCard, borderColor: "#ff4655" }}>
              <h3 style={{ ...styles.leagueName, color: "#ff4655" }}>CVAL</h3>
              <p style={styles.leagueDesc}>
                College VALORANT is the premier collegiate VALORANT league, featuring top university
                teams competing in organized seasonal play with professional production standards.
              </p>
            </div>
            <div style={{ ...styles.leagueCard, borderColor: "#c89b3c" }}>
              <h3 style={{ ...styles.leagueName, color: "#c89b3c" }}>CLOL</h3>
              <p style={styles.leagueDesc}>
                College League of Legends Championship is the official collegiate league for
                League of Legends, sanctioned by Riot Games with scholarship opportunities.
              </p>
            </div>
          </div>
        </section>

        {/* Roster */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>CSU Valorant Roster</h2>
          <div style={styles.tableWrapper}>
            <div style={styles.table}>
              <div style={{ ...styles.tableRow, ...styles.tableHeader }}>
                <div>IGN</div>
                <div>Name</div>
                <div>Role</div>
                <div>Major</div>
              </div>
              {CSU_VALORANT_ROSTER.map((player) => (
                <div key={player.ign} className="data-row" style={styles.tableRow}>
                  <div style={{ fontWeight: 600 }}>{player.ign}</div>
                  <div>{player.name}</div>
                  <div style={{ opacity: 0.9 }}>{player.role}</div>
                  <div style={{ opacity: 0.85 }}>{player.major}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Data Privacy */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Data Privacy</h2>
          <div style={styles.privacyGrid}>
            <div style={styles.privacyColumn}>
              <h4 style={styles.privacyHeading}>What We Collect</h4>
              <ul style={styles.list}>
                <li>Match history and performance statistics</li>
                <li>In-game name (Riot ID)</li>
                <li>Team affiliation and role</li>
                <li>Aggregate performance metrics (K/D, ACS, etc.)</li>
              </ul>
            </div>
            <div style={styles.privacyColumn}>
              <h4 style={styles.privacyHeading}>What We Never Access</h4>
              <ul style={styles.list}>
                <li>Account passwords or credentials</li>
                <li>Payment or billing information</li>
                <li>Personal contact information</li>
                <li>Private messages or social features</li>
                <li>Data from non-collegiate matches (unless public)</li>
              </ul>
            </div>
          </div>
          <p style={{ ...styles.text, marginTop: "1rem", opacity: 0.7 }}>
            Players can revoke access at any time via their Riot Games account settings.
          </p>
        </section>
      </div>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  container: {
    minHeight: "100dvh",
    backgroundColor: "#0d1526",
    color: "white",
    padding: "2rem",
  },
  content: {
    maxWidth: "900px",
    margin: "0 auto",
  },
  hero: {
    textAlign: "center",
    padding: "2rem 0 3rem",
  },
  heroTitle: {
    fontSize: "clamp(2rem, 5vw, 2.8rem)",
    fontWeight: 700,
    letterSpacing: "-0.03em",
    margin: 0,
    color: "#ffffff",
  },
  heroSubtitle: {
    fontSize: "1.1rem",
    opacity: 0.6,
    marginTop: "0.75rem",
    maxWidth: "520px",
    margin: "0.75rem auto 0",
    lineHeight: 1.6,
  },
  card: {
    border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.04)",
    borderRadius: 16,
    padding: "1.5rem",
    marginBottom: "1.25rem",
  },
  sectionTitle: {
    fontSize: "1.2rem",
    fontWeight: 600,
    marginTop: 0,
    marginBottom: "1rem",
    color: "rgba(255,255,255,0.9)",
    letterSpacing: "-0.01em",
  },
  text: {
    lineHeight: 1.7,
    opacity: 0.9,
    marginBottom: "0.75rem",
  },
  orderedList: {
    paddingLeft: "1.25rem",
    lineHeight: 2,
    opacity: 0.9,
  },
  privacyNote: {
    marginTop: "1rem",
    padding: "1rem",
    borderRadius: 12,
    background: "rgba(37, 99, 235, 0.15)",
    border: "1px solid rgba(37, 99, 235, 0.3)",
    fontSize: "0.95rem",
    lineHeight: 1.6,
  },
  leagueGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "1rem",
  },
  leagueCard: {
    padding: "1.25rem",
    borderRadius: 14,
    border: "2px solid",
    background: "rgba(0,0,0,0.2)",
  },
  leagueName: {
    fontSize: "1.3rem",
    margin: "0 0 0.5rem 0",
  },
  leagueDesc: {
    opacity: 0.85,
    lineHeight: 1.6,
    margin: 0,
    fontSize: "0.95rem",
  },
  tableWrapper: {
    overflowX: "auto",
  },
  table: {
    display: "grid",
    gap: "0.5rem",
    minWidth: "500px",
  },
  tableRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1.3fr 0.8fr 1.5fr",
    gap: "1rem",
    padding: "0.85rem 1rem",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(0,0,0,0.18)",
    alignItems: "center",
  },
  tableHeader: {
    background: "rgba(255,255,255,0.08)",
    fontWeight: 700,
  },
  privacyGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "1.5rem",
  },
  privacyColumn: {},
  privacyHeading: {
    fontSize: "1rem",
    fontWeight: 600,
    marginBottom: "0.5rem",
    color: "rgba(255,255,255,0.8)",
  },
  list: {
    margin: 0,
    paddingLeft: "1.1rem",
    opacity: 0.85,
    lineHeight: 1.8,
  },
};
