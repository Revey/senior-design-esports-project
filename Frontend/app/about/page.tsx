import type { CSSProperties } from "react";

export default function AboutPage() {
  return (
    <main style={styles.container}>
      <div style={styles.content}>
        {/* Hero */}
        <section style={styles.hero}>
          <h1 style={styles.heroTitle}>Campus Rankers</h1>
          <p style={styles.heroSubtitle}>
            Rankings, rosters, and match history for collegiate Valorant and
            League of Legends — across CVAL, CLOL, NACE, NECC, ECAC and more.
          </p>
        </section>

        {/* Mission */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Our Mission</h2>
          <p style={styles.text}>
            Campus Rankers is a public stats site for the collegiate
            <strong> Valorant (CVAL)</strong> and <strong>League of Legends (CLOL)</strong>{" "}
            scenes — modeled on what vlr.gg does for pro Valorant. Teams, players,
            schools, conferences, and seasons are all surfaced here so fans can
            follow their school and players can scout opponents.
          </p>
          <p style={styles.text}>
            More games (Rocket League, Overwatch, Smash, TFT, and others) are
            on the roadmap as the data shape for each is researched and added.
          </p>
        </section>

        {/* How RSO Works */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>How Riot Sign-On Works (and why)</h2>
          <p style={styles.text}>
            Player profiles default to private. Riot Sign-On (RSO) is the act
            of consent that flips a profile public:
          </p>
          <ol style={styles.orderedList}>
            <li>
              <strong>Connect Account</strong> — click <em>Connect Riot</em> in
              the navbar and you're redirected to Riot to authorize.
            </li>
            <li>
              <strong>Permission Granted</strong> — Campus Rankers receives
              read-only access to your match history, including the custom games
              that collegiate leagues use but Riot's public APIs don't expose.
            </li>
            <li>
              <strong>Profile Goes Public</strong> — your sign-in is your
              consent to display your in-game name, school, team association,
              and stats on the public site.
            </li>
            <li>
              <strong>Revoke Anytime</strong> — you can revoke consent from
              your account page; your profile drops back to private immediately,
              with full audit history kept.
            </li>
          </ol>
          <div style={styles.privacyNote}>
            <strong>Privacy:</strong> we only read match history. Never
            credentials, never payment data, never private messages. The
            consent gate is enforced at the database layer — non-consented
            players are never returned by the public API.
          </div>
        </section>

        {/* Leagues */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Leagues we track</h2>
          <div style={styles.leagueGrid}>
            <div style={{ ...styles.leagueCard, borderColor: "#ff4655" }}>
              <h3 style={{ ...styles.leagueName, color: "#ff4655" }}>CVAL</h3>
              <p style={styles.leagueDesc}>
                College VALORANT — the flagship collegiate Val league, top
                university teams in organized seasonal play with professional
                production.
              </p>
            </div>
            <div style={{ ...styles.leagueCard, borderColor: "#c89b3c" }}>
              <h3 style={{ ...styles.leagueName, color: "#c89b3c" }}>CLOL</h3>
              <p style={styles.leagueDesc}>
                College League of Legends Championship — Riot-sanctioned
                collegiate LoL with scholarship opportunities.
              </p>
            </div>
            <div style={{ ...styles.leagueCard, borderColor: "#5cd0a8" }}>
              <h3 style={{ ...styles.leagueName, color: "#5cd0a8" }}>NACE</h3>
              <p style={styles.leagueDesc}>
                National Association of Collegiate Esports — multi-game
                conferences (Premier, Plus, D1–D10) covering Val, LoL, and more.
              </p>
            </div>
            <div style={{ ...styles.leagueCard, borderColor: "#9aa6ff" }}>
              <h3 style={{ ...styles.leagueName, color: "#9aa6ff" }}>NECC, ECAC, others</h3>
              <p style={styles.leagueDesc}>
                Regional and conference-level collegiate leagues. Schools
                participate across multiple orgs; we track them all.
              </p>
            </div>
          </div>
        </section>

        {/* Data Privacy */}
        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Data privacy</h2>
          <div style={styles.privacyGrid}>
            <div style={styles.privacyColumn}>
              <h4 style={styles.privacyHeading}>What we collect (after RSO consent)</h4>
              <ul style={styles.list}>
                <li>Match history and performance statistics</li>
                <li>In-game name (Riot ID) and PUUID</li>
                <li>Team affiliation and role</li>
                <li>Aggregate metrics (K/D, ACS, CS, gold, etc.)</li>
              </ul>
            </div>
            <div style={styles.privacyColumn}>
              <h4 style={styles.privacyHeading}>What we never access</h4>
              <ul style={styles.list}>
                <li>Account passwords or credentials</li>
                <li>Payment or billing information</li>
                <li>Personal contact information</li>
                <li>Private messages or social features</li>
                <li>Data from non-collegiate matches (beyond public match metadata)</li>
              </ul>
            </div>
          </div>
          <p style={{ ...styles.text, marginTop: "1rem", opacity: 0.7 }}>
            Revoke consent anytime — your profile disappears from public listings
            immediately. Stored tokens are removed on the Riot Games side via
            your account settings.
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
