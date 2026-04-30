// valTeamSearchUtils.ts
// Utility functions and static team data for the Valorant team search page.
// Team data is sourced from the schools collection in MongoDB.
// Update this list whenever new schools / teams are added to the DB.

export interface ValTeam {
  teamName: string;
  school: string;
  /** Slug passed to /valorant/stats?team=<slug> */
  slug: string;
}

// All Valorant teams currently tracked in the system.
// CSU has two separate rosters (Green and CVAL circuit), so they get two entries.
export const VAL_TEAMS: ValTeam[] = [
  { teamName: "CSU Vikes Green",          school: "Cleveland State University",     slug: "CSU" },
  { teamName: "DePaul Valorant",          school: "DePaul University",              slug: "depaul-university" },
  { teamName: "Ohio State Valorant",      school: "Ohio State University",          slug: "ohio-state-university" },
  { teamName: "Penn State Valorant",      school: "Pennsylvania State University",  slug: "pennsylvania-state-university" },
  { teamName: "Columbia College",         school: "Columbia College",               slug: "columbia-college" },
  { teamName: "Michigan State Valorant",  school: "Michigan State University",      slug: "michigan-state-university" },
  { teamName: "Radford University",       school: "Radford University",             slug: "radford-university" },
  { teamName: "St Cloud State",           school: "St Cloud State University",      slug: "st-cloud-state-university" },
  { teamName: "Missouri Baptist",         school: "Missouri Baptist University",    slug: "missouri-baptist-university" },
  { teamName: "Briar Cliff",              school: "Briar Cliff University",         slug: "briar-cliff-university" },
];

/**
 * Filter teams by a search query. Matches against both teamName and school,
 * case-insensitively. Returns all teams if query is empty.
 */
export function filterValTeams(query: string): ValTeam[] {
  const q = query.trim().toLowerCase();
  if (!q) return VAL_TEAMS;
  return VAL_TEAMS.filter(
    (t) =>
      t.teamName.toLowerCase().includes(q) ||
      t.school.toLowerCase().includes(q)
  );
}
