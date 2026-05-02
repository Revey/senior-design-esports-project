import type { CSSProperties } from "react";

export default function PrivacyPolicyPage() {
  return (
    <main style={styles.container}>
      <div style={styles.content}>
        <h1 style={styles.title}>Privacy Policy</h1>
        <p style={styles.subtitle}>Last updated: April 5, 2026</p>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Overview</h2>
          <p style={styles.text}>
            Campus Rankers (&quot;we&quot;, &quot;our&quot;, &quot;the platform&quot;) is a
            collegiate esports stats site for Valorant and League of Legends — modeled after
            vlr.gg for the college scene. This privacy policy explains how we collect, use, and
            protect data obtained through our integration with the Riot Games API and Riot
            Sign-On (RSO).
          </p>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Information We Collect</h2>
          <p style={styles.text}>
            When you connect your Riot account via Riot Sign On, we receive and store:
          </p>
          <ul style={styles.list}>
            <li>Your Riot ID (in-game name and tag)</li>
            <li>Your PUUID (a unique player identifier used by Riot APIs)</li>
            <li>OAuth tokens (access, refresh, and identity tokens) to query your match history</li>
            <li>Match history data including performance statistics (kills, deaths, assists, combat score, etc.)</li>
            <li>Agent selections and map performance data</li>
          </ul>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Information We Never Access</h2>
          <ul style={styles.list}>
            <li>Account passwords or login credentials</li>
            <li>Payment or billing information</li>
            <li>Personal contact information (email, phone, address)</li>
            <li>Private messages or social features</li>
            <li>Data from non-collegiate matches unless publicly available</li>
            <li>MMR, Elo, or hidden ranking data</li>
          </ul>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>How We Use Your Data</h2>
          <ul style={styles.list}>
            <li>Display individual and team performance statistics for collegiate teams</li>
            <li>Track CVAL, CLOL, NACE, NECC, and ECAC match results and trends</li>
            <li>Help players and coaches analyze gameplay for improvement</li>
            <li>Aggregate team-level statistics (win rates, map performance, etc.)</li>
          </ul>
          <p style={styles.text}>
            We do not sell, share, or distribute your data to any third parties. Data is used
            exclusively for the purposes described above.
          </p>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Third-Party Services</h2>
          <ul style={styles.list}>
            <li>
              <strong>Riot Games API</strong> &mdash; Match data is retrieved via the official Riot Games
              API under our registered application. Riot Games&apos; own privacy policy applies to data
              processed on their servers.
            </li>
            <li>
              <strong>DigitalOcean Managed PostgreSQL</strong> &mdash; OAuth tokens and stats data
              are stored in a managed Postgres cluster with TLS-required connections and
              encryption at rest.
            </li>
            <li>
              <strong>DigitalOcean App Platform</strong> &mdash; The site is hosted on DigitalOcean.
              Standard web traffic logs (IP, browser type) may be collected as described in their
              privacy policy.
            </li>
          </ul>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Data Retention</h2>
          <p style={styles.text}>
            OAuth tokens are stored for as long as your account is linked. Match data and performance
            statistics are retained for the duration of the current collegiate season and may be
            archived for historical reference.
          </p>
          <p style={styles.text}>
            When you disconnect your account, your OAuth tokens are deleted immediately. Aggregated
            statistics that have already been computed may remain as part of team-level records.
          </p>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Your Rights</h2>
          <ul style={styles.list}>
            <li>
              <strong>Revoke access</strong> &mdash; You can revoke our access at any time through your
              Riot Games account settings at{" "}
              <a href="https://account.riotgames.com" style={styles.link}>
                account.riotgames.com
              </a>
            </li>
            <li>
              <strong>Disconnect</strong> &mdash; Use the &quot;Disconnect Account&quot; button on our
              Riot Sign On page to unlink your account and delete stored tokens
            </li>
            <li>
              <strong>Request deletion</strong> &mdash; Contact us to request full deletion of all
              your stored data
            </li>
          </ul>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Security</h2>
          <p style={styles.text}>
            All API keys and OAuth secrets are stored server-side and are never exposed in
            client-side code. Our site uses HTTPS for all communications. Session tokens are
            cryptographically signed and transmitted via HTTP-only cookies to prevent tampering
            and cross-site scripting attacks.
          </p>
        </section>

        <section style={styles.card}>
          <h2 style={styles.sectionTitle}>Contact</h2>
          <p style={styles.text}>
            For questions about this privacy policy or to request data deletion, reach out
            via the contact channel listed on the homepage of campusrankers.com.
          </p>
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
  title: {
    fontSize: "2.2rem",
    margin: 0,
    textAlign: "center",
  },
  subtitle: {
    textAlign: "center",
    opacity: 0.5,
    marginTop: "0.5rem",
    marginBottom: "2rem",
    fontSize: "0.9rem",
  },
  card: {
    border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: "1.5rem",
    marginBottom: "1.25rem",
  },
  sectionTitle: {
    fontSize: "1.3rem",
    marginTop: 0,
    marginBottom: "0.75rem",
    color: "#60a5fa",
  },
  text: {
    lineHeight: 1.7,
    opacity: 0.9,
    marginBottom: "0.75rem",
  },
  list: {
    margin: 0,
    paddingLeft: "1.25rem",
    opacity: 0.85,
    lineHeight: 1.9,
  },
  link: {
    color: "#60a5fa",
    textDecoration: "underline",
  },
};
