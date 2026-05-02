// UI helper: backend wire format is canonical lowercase ("valorant" / "lol").
// Display labels are TitleCase ("Valorant" / "League of Legends"). Phase 4
// of the postgres migration moved this mapping out of the API and into the
// frontend where it belongs as a UI concern.

export const GAME_LABELS: Record<string, string> = {
  valorant: "Valorant",
  lol: "League of Legends",
};

export function gameLabel(g: string | undefined | null): string {
  if (!g) return "";
  return GAME_LABELS[g] ?? g;
}

// Reverse: convert UI tab label back to wire enum (used when frontend stores
// the user's filter selection as a TitleCase tab name internally).
export const GAME_VALUES: Record<string, string> = {
  Valorant: "valorant",
  "League of Legends": "lol",
};

export function gameValue(label: string | undefined | null): string {
  if (!label || label === "All") return "";
  return GAME_VALUES[label] ?? label.toLowerCase();
}
