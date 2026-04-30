"use client";

import { Suspense, useState, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { CSSProperties } from "react";

// ─────────────────────────────────────────────
//  HARDCODED MATCH DATA  (from player_match_stats)
// ─────────────────────────────────────────────

type MatchRow = {
  map: string;
  agent: string;
  k: number;
  d: number;
  a: number;
  acs: number;
  fk: number;
  win: boolean;
};

type PlayerData = {
  id: string;
  label: string; // "Player 1", etc. — no real names in DB
  team: string;
  matches: MatchRow[];
};

const RAW_STATS: PlayerData[] = [
  // ── CSU Vikes Green ──────────────────────────────────────────────────────
  {
    id: "p1", label: "Player 1", team: "CSU Vikes Green",
    matches: [
      { map: "Corrode",  agent: "Yoru",    k:  9, d: 17, a:  3, acs: 149, fk: 2, win: false },
      { map: "Haven",    agent: "Jett",    k: 19, d: 19, a:  1, acs: 169, fk: 1, win: false },
      { map: "Abyss",    agent: "Jett",    k: 17, d:  6, a:  5, acs: 333, fk: 3, win: true  },
      { map: "Haven",    agent: "Chamber", k: 24, d:  8, a:  1, acs: 396, fk: 4, win: true  },
      { map: "Haven",    agent: "Chamber", k: 23, d:  5, a:  2, acs: 390, fk: 1, win: true  },
      { map: "Split",    agent: "Phoenix",  k: 10, d: 11, a:  5, acs: 182, fk: 3, win: true  },
      { map: "Split",    agent: "Waylay",  k: 21, d: 15, a:  6, acs: 240, fk: 2, win: true  },
      { map: "Haven",    agent: "Jett",    k: 18, d: 15, a:  2, acs: 261, fk: 2, win: true  },
      { map: "Haven",    agent: "Phoenix", k: 16, d: 12, a:  5, acs: 247, fk: 2, win: true  },
      { map: "Lotus",    agent: "Waylay",  k: 13, d: 16, a:  5, acs: 198, fk: 1, win: true  },
    ],
  },
  {
    id: "p2", label: "Player 2", team: "CSU Vikes Green",
    matches: [
      { map: "Corrode",  agent: "Viper",   k: 15, d: 14, a:  1, acs: 209, fk:  1, win: false },
      { map: "Haven",    agent: "Astra",   k:  9, d: 14, a:  5, acs: 128, fk:  0, win: false },
      { map: "Abyss",    agent: "Omen",    k: 11, d:  7, a:  8, acs: 189, fk:  0, win: true  },
      { map: "Haven",    agent: "Astra",   k:  9, d: 10, a:  6, acs: 148, fk:  1, win: true  },
      { map: "Haven",    agent: "Omen",    k: 14, d:  8, a:  7, acs: 240, fk:  2, win: true  },
      { map: "Split",    agent: "Sage",    k:  9, d: 10, a:  5, acs: 152, fk:  1, win: true  },
      { map: "Split",    agent: "Sage",    k: 11, d: 12, a:  9, acs: 196, fk:  2, win: true  },
      { map: "Haven",    agent: "Omen",    k: 12, d:  9, a:  8, acs: 201, fk:  2, win: true  },
      { map: "Haven",    agent: "Sage",    k: 10, d:  8, a:  7, acs: 190, fk:  1, win: true  },
      { map: "Lotus",    agent: "Omen",    k:  8, d: 11, a:  6, acs: 155, fk:  1, win: true  },
      { map: "Fracture", agent: "Viper",   k: 11, d:  9, a:  4, acs: 187, fk:  2, win: true  },
      { map: "Lotus",    agent: "Astra",   k:  9, d: 12, a:  5, acs: 162, fk:  1, win: true  },
      { map: "Haven",    agent: "Omen",    k: 10, d:  9, a:  6, acs: 178, fk:  1, win: false },
      { map: "Haven",    agent: "Viper",   k: 12, d: 11, a:  3, acs: 200, fk:  0, win: false },
    ],
  },
  {
    id: "p3", label: "Player 3", team: "CSU Vikes Green",
    matches: [
      { map: "Corrode",  agent: "Waylay",  k: 12, d: 14, a:  3, acs: 177, fk:  1, win: false },
      { map: "Haven",    agent: "Sova",    k: 13, d: 15, a:  6, acs: 171, fk:  1, win: false },
      { map: "Abyss",    agent: "Sova",    k: 12, d:  8, a:  5, acs: 209, fk:  1, win: true  },
      { map: "Haven",    agent: "Waylay",  k: 16, d:  9, a:  4, acs: 262, fk:  3, win: true  },
      { map: "Haven",    agent: "Sova",    k: 14, d:  8, a:  5, acs: 228, fk:  2, win: true  },
      { map: "Split",    agent: "Yoru",    k:  8, d: 10, a:  4, acs: 148, fk:  2, win: true  },
      { map: "Split",    agent: "Waylay",  k: 19, d: 13, a:  5, acs: 255, fk:  3, win: true  },
      { map: "Haven",    agent: "Sova",    k: 15, d: 12, a:  4, acs: 231, fk:  2, win: true  },
      { map: "Haven",    agent: "Waylay",  k: 14, d: 11, a:  5, acs: 215, fk:  2, win: true  },
      { map: "Lotus",    agent: "Sova",    k: 10, d: 13, a:  6, acs: 181, fk:  1, win: true  },
      { map: "Fracture", agent: "Yoru",    k: 11, d: 12, a:  4, acs: 178, fk:  2, win: true  },
      { map: "Lotus",    agent: "Sova",    k:  9, d: 10, a:  5, acs: 169, fk:  1, win: true  },
    ],
  },
  {
    id: "p4", label: "Player 4", team: "CSU Vikes Green",
    matches: [
      { map: "Corrode",  agent: "Sova",    k: 14, d: 14, a:  5, acs: 200, fk:  2, win: false },
      { map: "Haven",    agent: "Omen",    k: 12, d: 13, a:  7, acs: 183, fk:  1, win: false },
      { map: "Abyss",    agent: "Sova",    k: 14, d:  8, a:  6, acs: 235, fk:  2, win: true  },
      { map: "Haven",    agent: "Omen",    k: 15, d:  9, a:  5, acs: 248, fk:  2, win: true  },
      { map: "Haven",    agent: "Sova",    k: 14, d:  8, a:  6, acs: 236, fk:  2, win: true  },
      { map: "Split",    agent: "Waylay",  k:  9, d:  9, a:  5, acs: 165, fk:  1, win: true  },
      { map: "Split",    agent: "Omen",    k: 16, d: 10, a:  7, acs: 244, fk:  2, win: true  },
      { map: "Haven",    agent: "Sova",    k: 13, d:  9, a:  5, acs: 218, fk:  2, win: true  },
      { map: "Haven",    agent: "Omen",    k: 11, d:  8, a:  7, acs: 208, fk:  1, win: true  },
      { map: "Lotus",    agent: "Waylay",  k: 11, d: 12, a:  5, acs: 194, fk:  1, win: true  },
    ],
  },
  {
    id: "p5", label: "Player 5", team: "CSU Vikes Green",
    matches: [
      { map: "Corrode",  agent: "Cypher",  k:  7, d: 16, a:  3, acs: 118, fk:  0, win: false },
      { map: "Haven",    agent: "Neon",    k:  8, d: 15, a:  2, acs: 126, fk:  1, win: false },
      { map: "Abyss",    agent: "Cypher",  k:  9, d:  9, a:  4, acs: 166, fk:  0, win: true  },
      { map: "Haven",    agent: "Omen",    k: 10, d:  9, a:  5, acs: 175, fk:  1, win: true  },
      { map: "Haven",    agent: "Neon",    k: 11, d:  8, a:  3, acs: 188, fk:  1, win: true  },
      { map: "Split",    agent: "Cypher",  k:  6, d:  9, a:  3, acs: 118, fk:  0, win: true  },
      { map: "Split",    agent: "Neon",    k: 12, d: 10, a:  4, acs: 190, fk:  1, win: true  },
      { map: "Haven",    agent: "Omen",    k:  8, d: 11, a:  4, acs: 149, fk:  0, win: true  },
      { map: "Haven",    agent: "Cypher",  k:  7, d: 10, a:  4, acs: 143, fk:  0, win: true  },
      { map: "Lotus",    agent: "Omen",    k:  6, d: 11, a:  3, acs: 122, fk:  0, win: true  },
      { map: "Fracture", agent: "Cypher",  k:  8, d: 10, a:  3, acs: 146, fk:  0, win: true  },
      { map: "Lotus",    agent: "Neon",    k:  9, d: 11, a:  3, acs: 159, fk:  1, win: true  },
      { map: "Haven",    agent: "Cypher",  k:  6, d: 12, a:  4, acs: 127, fk:  0, win: false },
      { map: "Haven",    agent: "Omen",    k:  7, d: 10, a:  3, acs: 136, fk:  0, win: false },
    ],
  },
  {
    id: "p6", label: "Player 6", team: "CSU Vikes Green",
    matches: [
      { map: "Split",    agent: "Omen",    k:  9, d: 10, a:  5, acs: 178, fk:  1, win: true  },
      { map: "Lotus",    agent: "Breach",  k: 11, d: 11, a:  4, acs: 221, fk:  1, win: true  },
    ],
  },
  {
    id: "p7", label: "Player 7", team: "CSU Vikes Green",
    matches: [
      { map: "Fracture", agent: "Neon",    k:  5, d: 13, a:  2, acs:  72, fk:  0, win: true  },
      { map: "Lotus",    agent: "Waylay",  k:  6, d: 11, a:  3, acs: 112, fk:  0, win: true  },
      { map: "Haven",    agent: "Neon",    k:  4, d: 12, a:  2, acs:  81, fk:  0, win: false },
      { map: "Haven",    agent: "Waylay",  k:  5, d: 11, a:  2, acs: 103, fk:  0, win: false },
    ],
  },
  {
    id: "p8", label: "Player 8", team: "CSU Vikes Green",
    matches: [
      { map: "Fracture", agent: "Fade",    k: 12, d: 10, a:  4, acs: 188, fk:  1, win: true  },
      { map: "Lotus",    agent: "Killjoy", k: 10, d: 11, a:  3, acs: 158, fk:  1, win: true  },
      { map: "Haven",    agent: "Killjoy", k:  9, d: 12, a:  4, acs: 162, fk:  1, win: false },
      { map: "Haven",    agent: "Fade",    k: 11, d: 10, a:  4, acs: 183, fk:  1, win: false },
    ],
  },
  // ── Columbia College ────────────────────────────────────────────────────
  {
    id: "cc1", label: "Player 1", team: "Columbia College",
    matches: [
      { map: "Haven", agent: "Killjoy", k: 19, d: 10, a: 5, acs: 310, fk: 4, win: true },
      { map: "Haven", agent: "Vyse",    k: 15, d: 11, a: 4, acs: 262, fk: 3, win: true },
    ],
  },
  {
    id: "cc2", label: "Player 2", team: "Columbia College",
    matches: [
      { map: "Haven", agent: "Viper",   k: 14, d:  8, a: 4, acs: 211, fk: 1, win: true },
      { map: "Haven", agent: "Viper",   k: 12, d:  9, a: 4, acs: 191, fk: 2, win: true },
    ],
  },
  {
    id: "cc3", label: "Player 3", team: "Columbia College",
    matches: [
      { map: "Haven", agent: "Waylay",  k: 12, d:  9, a: 5, acs: 207, fk: 3, win: true },
      { map: "Haven", agent: "Yoru",    k: 11, d:  8, a: 4, acs: 189, fk: 2, win: true },
    ],
  },
  {
    id: "cc4", label: "Player 4", team: "Columbia College",
    matches: [
      { map: "Haven", agent: "Omen",    k: 10, d:  7, a: 6, acs: 235, fk: 1, win: true },
      { map: "Haven", agent: "Omen",    k:  9, d:  8, a: 5, acs: 217, fk: 1, win: true },
    ],
  },
  {
    id: "cc5", label: "Player 5", team: "Columbia College",
    matches: [
      { map: "Haven", agent: "Sova",    k: 11, d:  9, a: 6, acs: 187, fk: 2, win: true },
      { map: "Haven", agent: "Sova",    k:  9, d: 10, a: 5, acs: 173, fk: 1, win: true },
    ],
  },
  // ── DePaul University ───────────────────────────────────────────────────
  {
    id: "dp1", label: "Player 1", team: "DePaul University",
    matches: [
      { map: "Haven", agent: "Skye",    k: 14, d:  9, a: 6, acs: 214, fk: 2, win: true },
      { map: "Haven", agent: "Fade",    k: 12, d:  9, a: 5, acs: 190, fk: 1, win: true },
    ],
  },
  {
    id: "dp2", label: "Player 2", team: "DePaul University",
    matches: [
      { map: "Haven", agent: "Tejo",    k: 15, d: 10, a: 4, acs: 258, fk: 2, win: true },
      { map: "Haven", agent: "Viper",   k: 13, d: 10, a: 4, acs: 232, fk: 2, win: true },
    ],
  },
  {
    id: "dp3", label: "Player 3", team: "DePaul University",
    matches: [
      { map: "Haven", agent: "Brimstone", k:  8, d: 11, a: 5, acs: 142, fk: 0, win: true },
      { map: "Haven", agent: "Omen",    k:  7, d: 10, a: 5, acs: 126, fk: 0, win: true },
    ],
  },
  {
    id: "dp4", label: "Player 4", team: "DePaul University",
    matches: [
      { map: "Haven", agent: "Neon",    k: 10, d: 11, a: 3, acs: 155, fk: 1, win: true },
      { map: "Haven", agent: "Neon",    k:  9, d: 11, a: 2, acs: 137, fk: 1, win: true },
    ],
  },
  {
    id: "dp5", label: "Player 5", team: "DePaul University",
    matches: [
      { map: "Haven", agent: "Chamber", k: 17,  d: 10, a: 3, acs: 293, fk: 3, win: true },
      { map: "Haven", agent: "Veto",    k: 15,  d: 10, a: 3, acs: 267, fk: 2, win: true },
    ],
  },
  // ── Briar Cliff ─────────────────────────────────────────────────────────
  {
    id: "bc1", label: "Player 1", team: "briar cliff university",
    matches: [
      { map: "Haven", agent: "Sova",    k:  9, d: 13, a: 5, acs: 196, fk: 1, win: false },
      { map: "Haven", agent: "Sova",    k:  8, d: 13, a: 4, acs: 180, fk: 1, win: false },
    ],
  },
  {
    id: "bc2", label: "Player 2", team: "briar cliff university",
    matches: [
      { map: "Haven", agent: "Viper",   k:  9, d: 13, a: 4, acs: 192, fk: 1, win: false },
      { map: "Haven", agent: "Yoru",    k:  8, d: 13, a: 3, acs: 178, fk: 0, win: false },
    ],
  },
  {
    id: "bc3", label: "Player 3", team: "briar cliff university",
    matches: [
      { map: "Haven", agent: "Veto",    k:  7, d: 14, a: 3, acs: 144, fk: 0, win: false },
      { map: "Haven", agent: "Killjoy", k:  6, d: 14, a: 3, acs: 128, fk: 0, win: false },
    ],
  },
  {
    id: "bc4", label: "Player 4", team: "briar cliff university",
    matches: [
      { map: "Haven", agent: "Astra",   k:  4, d: 15, a: 3, acs: 101, fk: 0, win: false },
      { map: "Haven", agent: "Omen",    k:  4, d: 14, a: 3, acs:  97, fk: 0, win: false },
    ],
  },
  {
    id: "bc5", label: "Player 5", team: "briar cliff university",
    matches: [
      { map: "Haven", agent: "Neon",    k:  7, d: 13, a: 3, acs: 147, fk: 0, win: false },
      { map: "Haven", agent: "Waylay",  k:  6, d: 14, a: 3, acs: 133, fk: 0, win: false },
    ],
  },
  // ── St Cloud State ──────────────────────────────────────────────────────
  {
    id: "sc1", label: "Player 1", team: "st cloud state university",
    matches: [
      { map: "Haven", agent: "Yoru",    k:  6, d: 15, a: 2, acs: 153, fk: 0, win: false },
      { map: "Haven", agent: "Neon",    k:  5, d: 14, a: 2, acs: 139, fk: 0, win: false },
    ],
  },
  {
    id: "sc2", label: "Player 2", team: "st cloud state university",
    matches: [
      { map: "Haven", agent: "Chamber", k:  4, d: 15, a: 2, acs: 114, fk: 0, win: false },
      { map: "Haven", agent: "Cypher",  k:  3, d: 16, a: 2, acs: 102, fk: 0, win: false },
    ],
  },
  {
    id: "sc3", label: "Player 3", team: "st cloud state university",
    matches: [
      { map: "Haven", agent: "Fade",    k:  9, d: 13, a: 4, acs: 218, fk: 1, win: false },
      { map: "Haven", agent: "Sova",    k:  8, d: 13, a: 4, acs: 206, fk: 1, win: false },
    ],
  },
  {
    id: "sc4", label: "Player 4", team: "st cloud state university",
    matches: [
      { map: "Haven", agent: "Sova",    k:  2, d: 16, a: 1, acs:  52, fk: 0, win: false },
      { map: "Haven", agent: "Yoru",    k:  2, d: 15, a: 1, acs:  46, fk: 0, win: false },
    ],
  },
  {
    id: "sc5", label: "Player 5", team: "st cloud state university",
    matches: [
      { map: "Haven", agent: "Omen",    k:  9, d: 12, a: 4, acs: 239, fk: 1, win: false },
      { map: "Haven", agent: "Omen",    k:  8, d: 12, a: 4, acs: 225, fk: 1, win: false },
    ],
  },
  // ── Michigan State ──────────────────────────────────────────────────────
  {
    id: "ms1", label: "Player 1", team: "Michigan State University",
    matches: [
      { map: "Haven", agent: "Fade",    k:  8, d: 13, a: 4, acs: 173, fk: 1, win: false },
      { map: "Haven", agent: "Sova",    k:  7, d: 13, a: 4, acs: 163, fk: 0, win: false },
    ],
  },
  {
    id: "ms2", label: "Player 2", team: "Michigan State University",
    matches: [
      { map: "Haven", agent: "Neon",    k:  8, d: 13, a: 3, acs: 162, fk: 1, win: false },
      { map: "Haven", agent: "Waylay",  k:  7, d: 13, a: 3, acs: 154, fk: 0, win: false },
    ],
  },
  {
    id: "ms3", label: "Player 3", team: "Michigan State University",
    matches: [
      { map: "Haven", agent: "Yoru",    k: 11, d: 13, a: 4, acs: 247, fk: 2, win: false },
      { map: "Haven", agent: "Yoru",    k: 10, d: 12, a: 4, acs: 237, fk: 1, win: false },
    ],
  },
  {
    id: "ms4", label: "Player 4", team: "Michigan State University",
    matches: [
      { map: "Haven", agent: "Omen",    k:  5, d: 13, a: 3, acs:  88, fk: 0, win: false },
      { map: "Haven", agent: "Omen",    k:  4, d: 13, a: 3, acs:  78, fk: 0, win: false },
    ],
  },
  {
    id: "ms5", label: "Player 5", team: "Michigan State University",
    matches: [
      { map: "Haven", agent: "Viper",   k: 10, d: 12, a: 4, acs: 208, fk: 1, win: false },
      { map: "Haven", agent: "Killjoy", k:  9, d: 12, a: 4, acs: 200, fk: 1, win: false },
    ],
  },
  // ── Penn State ──────────────────────────────────────────────────────────
  {
    id: "ps1", label: "Player 1", team: "Pennsylvania State University",
    matches: [
      { map: "Haven", agent: "Vyse",    k:  8, d: 14, a: 4, acs: 151, fk: 1, win: false },
      { map: "Haven", agent: "Sova",    k:  7, d: 14, a: 4, acs: 141, fk: 0, win: false },
    ],
  },
  {
    id: "ps2", label: "Player 2", team: "Pennsylvania State University",
    matches: [
      { map: "Haven", agent: "Cypher",  k:  7, d: 13, a: 4, acs: 138, fk: 0, win: false },
      { map: "Haven", agent: "Omen",    k:  6, d: 13, a: 4, acs: 126, fk: 0, win: false },
    ],
  },
  {
    id: "ps3", label: "Player 3", team: "Pennsylvania State University",
    matches: [
      { map: "Haven", agent: "Miks",    k: 12, d: 12, a: 4, acs: 270, fk: 2, win: false },
      { map: "Haven", agent: "Waylay",  k: 11, d: 12, a: 4, acs: 258, fk: 1, win: false },
    ],
  },
  {
    id: "ps4", label: "Player 4", team: "Pennsylvania State University",
    matches: [
      { map: "Haven", agent: "Yoru",    k:  8, d: 14, a: 3, acs: 165, fk: 1, win: false },
      { map: "Haven", agent: "Neon",    k:  7, d: 14, a: 3, acs: 155, fk: 0, win: false },
    ],
  },
  {
    id: "ps5", label: "Player 5", team: "Pennsylvania State University",
    matches: [
      { map: "Haven", agent: "Omen",    k: 11, d: 12, a: 5, acs: 235, fk: 1, win: false },
      { map: "Haven", agent: "Waylay",  k: 10, d: 12, a: 5, acs: 225, fk: 1, win: false },
    ],
  },
];

// ─────────────────────────────────────────────
//  COMPUTED AGGREGATES
// ─────────────────────────────────────────────

type AgentCount = { agent: string; count: number };

type ComputedPlayer = {
  id: string;
  label: string;
  team: string;
  games: number;
  wins: number;
  avgACS: number;
  avgKD: number;
  avgK: number;
  avgD: number;
  avgA: number;
  totalFK: number;
  agents: AgentCount[];
  matches: MatchRow[];
};

function computePlayer(p: PlayerData): ComputedPlayer {
  const real = p.matches.filter((m) => m.agent !== "");
  const games = real.length;
  const wins = real.filter((m) => m.win).length;
  const avgK = real.reduce((s, m) => s + m.k, 0) / Math.max(games, 1);
  const avgD = real.reduce((s, m) => s + m.d, 0) / Math.max(games, 1);
  const avgA = real.reduce((s, m) => s + m.a, 0) / Math.max(games, 1);
  const avgACS = real.reduce((s, m) => s + m.acs, 0) / Math.max(games, 1);
  const avgKD = avgD > 0 ? avgK / avgD : avgK;
  const totalFK = real.reduce((s, m) => s + m.fk, 0);

  const agentMap = new Map<string, number>();
  for (const m of real) {
    if (m.agent) agentMap.set(m.agent, (agentMap.get(m.agent) ?? 0) + 1);
  }
  const agents = [...agentMap.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([agent, count]) => ({ agent, count }));

  return {
    id: p.id,
    label: p.label,
    team: p.team,
    games,
    wins,
    avgACS: Math.round(avgACS),
    avgKD: parseFloat(avgKD.toFixed(2)),
    avgK: parseFloat(avgK.toFixed(1)),
    avgD: parseFloat(avgD.toFixed(1)),
    avgA: parseFloat(avgA.toFixed(1)),
    totalFK,
    agents,
    matches: p.matches,
  };
}

const ALL_COMPUTED = RAW_STATS.map(computePlayer);

function getTeamPlayers(teamName: string): ComputedPlayer[] {
  const t = teamName.toLowerCase();
  return ALL_COMPUTED.filter((p) => p.team.toLowerCase() === t);
}

const TEAM_NAMES = [...new Set(RAW_STATS.map((p) => p.team))];

function normalizeTeam(slug: string): string {
  const s = decodeURIComponent(slug).toLowerCase().trim();
  if (s === "csu") return "CSU Vikes Green";
  return TEAM_NAMES.find((t) => t.toLowerCase() === s) ?? slug;
}

// ─────────────────────────────────────────────
//  AGENT COLOUR MAP  (Valorant palette)
// ─────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  Jett:      "#b8d8f8", Chamber: "#d4a96a", Phoenix: "#f97316",
  Waylay:    "#a78bfa", Yoru:    "#60a5fa", Neon:    "#34d399",
  Viper:     "#4ade80", Omen:    "#c084fc", Astra:   "#e879f9",
  Cypher:    "#94a3b8", Sage:    "#86efac", Sova:    "#7dd3fc",
  Killjoy:   "#fbbf24", Fade:    "#f472b6", Breach:  "#fb923c",
  Skye:      "#6ee7b7", Tejo:    "#f87171", Brimstone: "#fca5a5",
  Vyse:      "#c7d2fe", Miks:    "#d1fae5", Veto:    "#fde68a",
};
function agentColor(a: string): string {
  return AGENT_COLORS[a] ?? "#94a3b8";
}

// ─────────────────────────────────────────────
//  PLAYER CARD
// ─────────────────────────────────────────────

function StatPill({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div style={S.pill}>
      <div style={{ ...S.pillValue, color: accent ?? "white" }}>{value}</div>
      <div style={S.pillLabel}>{label}</div>
    </div>
  );
}

function PlayerCard({ player, accent }: { player: ComputedPlayer; accent: string }) {
  const [open, setOpen] = useState(false);
  const winPct = player.games > 0 ? Math.round((player.wins / player.games) * 100) : 0;
  const maxAgentCount = player.agents[0]?.count ?? 1;

  const kdColor =
    player.avgKD >= 1.4 ? "#4ade80" :
    player.avgKD >= 1.0 ? "#fbbf24" : "#f87171";

  const acsColor =
    player.avgACS >= 250 ? "#4ade80" :
    player.avgACS >= 170 ? "#fbbf24" : "#f87171";

  return (
    <article style={{ ...S.card, borderColor: `${accent}33` }}>
      {/* Card top stripe */}
      <div style={{ ...S.cardStripe, background: `linear-gradient(90deg, ${accent}22 0%, transparent 100%)` }} />

      {/* Header */}
      <div style={S.cardHead}>
        <div>
          <div style={S.playerLabel}>{player.label}</div>
          <div style={S.winTag}>
            <span style={{ color: accent, fontWeight: 700 }}>{player.wins}W</span>
            <span style={{ opacity: 0.4, margin: "0 4px" }}>·</span>
            <span style={{ opacity: 0.6 }}>{player.games - player.wins}L</span>
            <span style={{ opacity: 0.35, margin: "0 4px" }}>·</span>
            <span style={{ opacity: 0.6 }}>{winPct}% WR</span>
          </div>
        </div>
        <div style={S.gpBadge}>{player.games} GP</div>
      </div>

      {/* Stat pills */}
      <div style={S.pillRow}>
        <StatPill label="ACS"   value={player.avgACS} accent={acsColor} />
        <StatPill label="K/D"   value={player.avgKD}  accent={kdColor}  />
        <StatPill label="Kills" value={player.avgK}   />
        <StatPill label="Deaths" value={player.avgD}  />
        <StatPill label="Assists" value={player.avgA} />
        <StatPill label="First Kills" value={player.totalFK} />
      </div>

      {/* Agent pool */}
      {player.agents.length > 0 && (
        <div style={S.agentSection}>
          <div style={S.sectionHead}>Agent Pool</div>
          {player.agents.map(({ agent, count }) => (
            <div key={agent} style={S.agentRow}>
              <div style={{ ...S.agentName, color: agentColor(agent) }}>{agent}</div>
              <div style={S.barTrack}>
                <div
                  style={{
                    ...S.barFill,
                    width: `${(count / maxAgentCount) * 100}%`,
                    background: agentColor(agent),
                  }}
                />
              </div>
              <div style={S.agentCount}>{count}</div>
            </div>
          ))}
        </div>
      )}

      {/* Match history toggle */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{ ...S.historyToggle, borderColor: `${accent}40`, color: accent }}
      >
        {open ? "▲ Hide matches" : "▼ Show matches"} ({player.matches.length})
      </button>

      {open && (
        <div style={S.matchTable}>
          {/* Header */}
          <div style={{ ...S.matchRow, ...S.matchHeader }}>
            <div style={S.mMap}>Map</div>
            <div style={S.mAgent}>Agent</div>
            <div style={S.mStat}>K</div>
            <div style={S.mStat}>D</div>
            <div style={S.mStat}>A</div>
            <div style={S.mStat}>ACS</div>
            <div style={S.mStat}>FK</div>
            <div style={S.mResult}>Result</div>
          </div>
          {player.matches.map((m, i) => (
            <div
              key={i}
              style={{
                ...S.matchRow,
                background: i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent",
              }}
            >
              <div style={{ ...S.mMap, opacity: 0.8 }}>{m.map || "No Show"}</div>
              <div style={{ ...S.mAgent, color: agentColor(m.agent), fontWeight: 600 }}>
                {m.agent || "—"}
              </div>
              <div style={S.mStat}>{m.k || "—"}</div>
              <div style={S.mStat}>{m.d || "—"}</div>
              <div style={S.mStat}>{m.a || "—"}</div>
              <div style={S.mStat}>{m.acs || "—"}</div>
              <div style={S.mStat}>{m.fk}</div>
              <div style={S.mResult}>
                <span style={{
                  ...S.resultPill,
                  background: m.win ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)",
                  color:      m.win ? "#4ade80"               : "#f87171",
                }}>
                  {m.win ? "W" : "L"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

// ─────────────────────────────────────────────
//  TEAM OVERVIEW BAR
// ─────────────────────────────────────────────

function TeamOverview({ players, accent }: { players: ComputedPlayer[]; accent: string }) {
  const allMatches = players.flatMap((p) => p.matches.filter((m) => m.agent !== ""));
  const totalGames = new Set(players.flatMap((p) =>
    p.matches.map((_, i) => `${p.id}-${i}`)
  )).size;
  const wins = players.reduce((s, p) => s + p.wins, 0);
  const totalGP = players.reduce((s, p) => s + p.games, 0);
  const avgACS = totalGP > 0
    ? Math.round(allMatches.reduce((s, m) => s + m.acs, 0) / Math.max(allMatches.length, 1))
    : 0;
  const allK = allMatches.reduce((s, m) => s + m.k, 0);
  const allD = allMatches.reduce((s, m) => s + m.d, 0);
  const teamKD = allD > 0 ? (allK / allD).toFixed(2) : "—";
  const totalFK = players.reduce((s, p) => s + p.totalFK, 0);

  // Unique match wins/losses (per player games)
  const playerGames = players[0]?.games ?? 0;
  const teamWins = players[0]?.wins ?? 0;
  const record = playerGames > 0 ? `${teamWins}W – ${playerGames - teamWins}L` : "—";

  return (
    <div style={{ ...S.overviewBar, borderColor: `${accent}44` }}>
      <div style={S.overviewItem}>
        <div style={{ ...S.overviewValue, color: accent }}>{record}</div>
        <div style={S.overviewLabel}>Team Record</div>
      </div>
      <div style={S.overviewDivider} />
      <div style={S.overviewItem}>
        <div style={S.overviewValue}>{avgACS}</div>
        <div style={S.overviewLabel}>Avg Team ACS</div>
      </div>
      <div style={S.overviewDivider} />
      <div style={S.overviewItem}>
        <div style={S.overviewValue}>{teamKD}</div>
        <div style={S.overviewLabel}>Team K/D</div>
      </div>
      <div style={S.overviewDivider} />
      <div style={S.overviewItem}>
        <div style={S.overviewValue}>{totalFK}</div>
        <div style={S.overviewLabel}>Total First Kills</div>
      </div>
      <div style={S.overviewDivider} />
      <div style={S.overviewItem}>
        <div style={S.overviewValue}>{players.length}</div>
        <div style={S.overviewLabel}>Rostered Players</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
//  SORT CONTROLS
// ─────────────────────────────────────────────

type SortKey = "avgACS" | "avgKD" | "wins" | "totalFK";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "avgACS", label: "ACS" },
  { key: "avgKD",  label: "K/D" },
  { key: "wins",   label: "Wins" },
  { key: "totalFK", label: "First Kills" },
];

// ─────────────────────────────────────────────
//  PAGE INNER
// ─────────────────────────────────────────────

const ACCENT = "#ff4655"; // Valorant red

function ValorantStatsInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const teamSlug = searchParams.get("team") ?? "CSU";
  const teamName = normalizeTeam(teamSlug);

  const [sortKey, setSortKey] = useState<SortKey>("avgACS");

  const players = useMemo(() => getTeamPlayers(teamName), [teamName]);

  const sorted = useMemo(
    () => [...players].sort((a, b) => b[sortKey] - a[sortKey]),
    [players, sortKey]
  );

  const notFound = players.length === 0;

  return (
    <main style={S.page}>
      {/* Google Font */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@400;500;600&display=swap');
        * { box-sizing: border-box; }
        body { font-family: 'Barlow', sans-serif; }
      `}</style>

      <div style={S.inner}>
        {/* Top bar */}
        <div style={S.topBar}>
          <button type="button" onClick={() => router.push("/valorant")} style={S.backBtn}>
            ← Back
          </button>
          <span style={S.gamePill}>VALORANT</span>
        </div>

        {/* Hero */}
        <header style={S.hero}>
          <div style={S.heroAccent} />
          <h1 style={S.title}>{teamName}</h1>
          <p style={S.kicker}>Team Stats · Season 2025</p>
        </header>

        {notFound ? (
          <div style={S.notFound}>
            No stats found for <strong>{teamName}</strong>. Stats are available for CSU Vikes Green and other tracked teams.
          </div>
        ) : (
          <>
            {/* Overview */}
            <TeamOverview players={players} accent={ACCENT} />

            {/* Sort bar */}
            <div style={S.sortBar}>
              <span style={S.sortLabel}>Sort by</span>
              {SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setSortKey(opt.key)}
                  style={{
                    ...S.sortBtn,
                    background: sortKey === opt.key ? ACCENT : "rgba(255,255,255,0.06)",
                    color:      sortKey === opt.key ? "white" : "rgba(255,255,255,0.5)",
                    borderColor: sortKey === opt.key ? ACCENT : "rgba(255,255,255,0.1)",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Player grid */}
            <div style={S.grid}>
              {sorted.map((p) => (
                <PlayerCard key={p.id} player={p} accent={ACCENT} />
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}

export default function ValorantStatsPage() {
  return (
    <Suspense
      fallback={
        <main style={{ minHeight: "100vh", backgroundColor: "#0a0e1a", color: "white", padding: "2rem" }}>
          Loading…
        </main>
      }
    >
      <ValorantStatsInner />
    </Suspense>
  );
}

// ─────────────────────────────────────────────
//  STYLES
// ─────────────────────────────────────────────

const S: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    backgroundColor: "#0a0e1a",
    color: "white",
    padding: "2rem 1.25rem 5rem",
    fontFamily: "'Barlow', sans-serif",
  },
  inner: {
    width: "min(1200px, 100%)",
    margin: "0 auto",
  },

  // Nav
  topBar: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    marginBottom: "1.5rem",
  },
  backBtn: {
    padding: "0.5rem 1rem",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "transparent",
    color: "rgba(255,255,255,0.6)",
    cursor: "pointer",
    fontSize: "0.9rem",
    fontFamily: "'Barlow', sans-serif",
  },
  gamePill: {
    padding: "0.3rem 0.75rem",
    borderRadius: 6,
    background: "rgba(255,70,85,0.15)",
    color: "#ff4655",
    fontSize: "0.72rem",
    fontWeight: 700,
    letterSpacing: "0.1em",
    border: "1px solid rgba(255,70,85,0.3)",
  },

  // Hero
  hero: {
    position: "relative",
    marginBottom: "1.75rem",
    paddingLeft: "1rem",
  },
  heroAccent: {
    position: "absolute",
    left: 0,
    top: 4,
    bottom: 4,
    width: 4,
    borderRadius: 2,
    background: "#ff4655",
  },
  title: {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: "clamp(2.2rem, 5vw, 3.5rem)",
    fontWeight: 800,
    letterSpacing: "-0.01em",
    margin: 0,
    lineHeight: 1,
  },
  kicker: {
    fontSize: "0.82rem",
    opacity: 0.45,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    marginTop: "0.4rem",
  },

  // Overview bar
  overviewBar: {
    display: "flex",
    flexWrap: "wrap",
    gap: 0,
    border: "1px solid",
    borderRadius: 14,
    background: "rgba(255,255,255,0.03)",
    marginBottom: "1.25rem",
    overflow: "hidden",
  },
  overviewItem: {
    flex: "1 1 120px",
    padding: "1rem 1.25rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.2rem",
  },
  overviewValue: {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: "1.8rem",
    fontWeight: 700,
    lineHeight: 1,
  },
  overviewLabel: {
    fontSize: "0.72rem",
    opacity: 0.45,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  overviewDivider: {
    width: 1,
    background: "rgba(255,255,255,0.07)",
    alignSelf: "stretch",
  },

  // Sort
  sortBar: {
    display: "flex",
    gap: "0.5rem",
    alignItems: "center",
    marginBottom: "1rem",
    flexWrap: "wrap",
  },
  sortLabel: {
    fontSize: "0.8rem",
    opacity: 0.4,
    marginRight: "0.25rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  sortBtn: {
    padding: "0.35rem 0.85rem",
    borderRadius: 7,
    border: "1px solid",
    cursor: "pointer",
    fontSize: "0.82rem",
    fontWeight: 600,
    fontFamily: "'Barlow', sans-serif",
    transition: "background 0.12s, color 0.12s",
  },

  // Grid
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
    gap: "1rem",
  },

  // Card
  card: {
    position: "relative",
    background: "rgba(255,255,255,0.03)",
    border: "1px solid",
    borderRadius: 16,
    padding: "1.25rem",
    overflow: "hidden",
  },
  cardStripe: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 3,
  },
  cardHead: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "1rem",
  },
  playerLabel: {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: "1.3rem",
    fontWeight: 700,
    letterSpacing: "0.02em",
  },
  winTag: {
    fontSize: "0.82rem",
    marginTop: "0.2rem",
    display: "flex",
    alignItems: "center",
  },
  gpBadge: {
    padding: "0.25rem 0.6rem",
    borderRadius: 6,
    background: "rgba(255,255,255,0.07)",
    fontSize: "0.75rem",
    fontWeight: 600,
    opacity: 0.7,
  },

  // Stat pills
  pillRow: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: "0.5rem",
    marginBottom: "1rem",
  },
  pill: {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 10,
    padding: "0.55rem 0.65rem",
    textAlign: "center",
  },
  pillValue: {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: "1.35rem",
    fontWeight: 700,
    lineHeight: 1,
  },
  pillLabel: {
    fontSize: "0.65rem",
    opacity: 0.45,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    marginTop: "0.2rem",
  },

  // Agent pool
  agentSection: {
    marginBottom: "1rem",
  },
  sectionHead: {
    fontSize: "0.7rem",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    opacity: 0.4,
    marginBottom: "0.55rem",
  },
  agentRow: {
    display: "grid",
    gridTemplateColumns: "80px 1fr 24px",
    alignItems: "center",
    gap: "0.6rem",
    marginBottom: "0.35rem",
  },
  agentName: {
    fontSize: "0.85rem",
    fontWeight: 600,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  barTrack: {
    height: 6,
    borderRadius: 3,
    background: "rgba(255,255,255,0.07)",
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 3,
    opacity: 0.75,
  },
  agentCount: {
    fontSize: "0.75rem",
    opacity: 0.5,
    textAlign: "right",
  },

  // Match history toggle
  historyToggle: {
    width: "100%",
    padding: "0.5rem",
    borderRadius: 8,
    border: "1px solid",
    background: "transparent",
    cursor: "pointer",
    fontSize: "0.8rem",
    fontWeight: 600,
    fontFamily: "'Barlow', sans-serif",
    letterSpacing: "0.04em",
    marginBottom: "0",
    transition: "opacity 0.12s",
  },

  // Match table
  matchTable: {
    marginTop: "0.65rem",
    borderRadius: 10,
    overflow: "hidden",
    border: "1px solid rgba(255,255,255,0.07)",
  },
  matchHeader: {
    background: "rgba(255,255,255,0.06)",
    fontSize: "0.68rem",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    opacity: 0.65,
    fontWeight: 700,
  },
  matchRow: {
    display: "grid",
    gridTemplateColumns: "90px 70px repeat(5, 1fr) 44px",
    gap: "0.25rem",
    padding: "0.5rem 0.6rem",
    alignItems: "center",
    fontSize: "0.82rem",
    borderBottom: "1px solid rgba(255,255,255,0.04)",
  },
  mMap:    { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  mAgent:  { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.8rem" },
  mStat:   { textAlign: "center" },
  mResult: { textAlign: "center" },
  resultPill: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 24,
    height: 20,
    borderRadius: 4,
    fontWeight: 700,
    fontSize: "0.72rem",
  },

  // Not found
  notFound: {
    padding: "2rem",
    borderRadius: 14,
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.1)",
    opacity: 0.7,
    lineHeight: 1.6,
  },
};