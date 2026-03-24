// teamSearchUtils.ts
// Utility functions and static team data for the League team search page.
// Team data is sourced from Backend/League/clol_teams_puuids.json

export interface CollegeTeam {
  teamName: string;
  school: string;
}

// All 32 teams from the 2025 CLOL Championship.
// Update this list by re-running scrape_clol.py whenever the roster changes.
export const CLOL_TEAMS: CollegeTeam[] = [
  { teamName: "NOVA Nighthawks",                       school: "Northern Virginia Community College" },
  { teamName: "Purdue Gold",                           school: "Purdue University" },
  { teamName: "Maryville University",                  school: "Maryville University" },
  { teamName: "The Ohio State University",             school: "The Ohio State University" },
  { teamName: "Purdue Northwest",                      school: "Purdue University Northwest" },
  { teamName: "Fisher College",                        school: "Fisher College" },
  { teamName: "Northwood University",                  school: "Northwood University" },
  { teamName: "Stony Brook Esports",                   school: "Stony Brook University" },
  { teamName: "Ball State",                            school: "Ball State University" },
  { teamName: "San Jose State Esports - LOL",          school: "San Jose State University" },
  { teamName: "RCU League of Legends",                 school: "RCU" },
  { teamName: "Converse University League of Legends", school: "Converse University" },
  { teamName: "Cal Golden Bears",                      school: "University of California - Berkeley" },
  { teamName: "UCI Esports",                           school: "University of California - Irvine" },
  { teamName: "Texas League Premier",                  school: "University of Texas at Austin" },
  { teamName: "UST LoL",                               school: "University of St. Thomas" },
  { teamName: "OC Esports Varsity LoL",                school: "Oklahoma Christian University" },
  { teamName: "Bethany Esports",                       school: "Bethany Lutheran College" },
  { teamName: "CSUN LoL Black",                        school: "California State University - Northridge" },
  { teamName: "Ole Miss Esports",                      school: "University of Mississippi" },
  { teamName: "Western Mustangs",                      school: "Western University" },
  { teamName: "UHSP Eutectics",                        school: "University of Health Sciences & Pharmacy in St Louis" },
  { teamName: "GV Vikings",                            school: "Grand View University" },
  { teamName: "UTM Phoenix",                           school: "University of Toronto Mississauga" },
  { teamName: "UMN Maroon",                            school: "University of Minnesota - Twin Cities" },
  { teamName: "Weber State University",                school: "Weber State University" },
  { teamName: "Winthrop University",                   school: "Winthrop University" },
  { teamName: "St Clair Saints",                       school: "St. Clair College" },
  { teamName: "Carleton Ravens",                       school: "Carleton University" },
  { teamName: "USF Gold",                              school: "University of South Florida" },
  { teamName: "SCAD Esports",                          school: "Savannah College of Art and Design" },
  { teamName: "Illinois State University",             school: "Illinois State University" },
];

/**
 * Filter teams by a search query. Matches against both teamName and school,
 * case-insensitively. Returns all teams if query is empty.
 */
export function filterTeams(query: string): CollegeTeam[] {
  const q = query.trim().toLowerCase();
  if (!q) return CLOL_TEAMS;
  return CLOL_TEAMS.filter(
    (t) =>
      t.teamName.toLowerCase().includes(q) ||
      t.school.toLowerCase().includes(q)
  );
}

/**
 * Convert a team name into a URL-safe slug for the stats route query param.
 * e.g. "Cal Golden Bears" → "Cal+Golden+Bears"
 */
export function teamToSlug(teamName: string): string {
  return encodeURIComponent(teamName);
}
