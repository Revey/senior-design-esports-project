"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

type GameModifier = "val" | "lol" | "tft" | "ow" | "rl";

interface Game {
  slug: string;
  name: string;
  tag: string;
  href: string;
  image: string;
  modifier: GameModifier;
  disabled: boolean;
}

const GAMES: Game[] = [
  {
    slug: "valorant",
    name: "Valorant",
    tag: "CVAL · 5v5 tactical",
    href: "/valorant",
    image: "/images/valorantimage.png",
    modifier: "val",
    disabled: false,
  },
  {
    slug: "league",
    name: "League of Legends",
    tag: "CLOL · 5v5 MOBA",
    href: "/league",
    image: "/images/league-of-legends.png",
    modifier: "lol",
    disabled: false,
  },
  {
    slug: "tft",
    name: "Teamfight Tactics",
    tag: "TFT · Auto Battler",
    href: "/tft",
    image: "/images/tft.png",
    modifier: "tft",
    disabled: true,
  },
  {
    slug: "overwatch",
    name: "Overwatch 2",
    tag: "OW · 5v5 Hero Shooter",
    href: "/overwatch",
    image: "/images/overwatch.png",
    modifier: "ow",
    disabled: true,
  },
  {
    slug: "rocket-league",
    name: "Rocket League",
    tag: "RL · 3v3 Vehicular",
    href: "/rocket-league",
    image: "/images/rocket-league.png",
    modifier: "rl",
    disabled: true,
  },
];

const activeGames = GAMES.filter((g) => !g.disabled);
const comingSoonGames = GAMES.filter((g) => g.disabled);

function ArrowIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GameCard({ g, onClick }: { g: Game; onClick?: () => void }) {
  return (
    <button
      key={g.slug}
      type="button"
      className={`game-card game-card--${g.modifier}${g.disabled ? " game-card--coming-soon" : ""}`}
      onClick={onClick}
      aria-label={g.disabled ? `${g.name} — coming soon` : `Open ${g.name} stats`}
      aria-disabled={g.disabled}
    >
      <div className="game-shell">
        <div className="game-core">
          <div className="game-image-wrap">
            <Image
              src={g.image}
              alt={`${g.name} artwork`}
              fill
              sizes="(max-width: 768px) 320px, 280px"
              style={{ objectFit: "contain" }}
              priority={g.modifier === "val"}
            />
            {g.disabled && (
              <div className="game-coming-soon-badge" aria-hidden="true">
                Coming Soon
              </div>
            )}
          </div>

          <div className="game-meta">
            <div className="game-name">{g.name}</div>
            <div className="game-tag">{g.tag}</div>
          </div>

          <div className="game-cta">
            <span>{g.disabled ? "Coming soon" : "Enter rankings"}</span>
            {!g.disabled && (
              <span className="game-cta-icon" aria-hidden="true">
                <ArrowIcon />
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}

export default function Home() {
  const router = useRouter();

  return (
    <main className="home-page">
      <div className="home-bg" aria-hidden="true" />
      <div className="home-grain" aria-hidden="true" />

      <div className="home-content">
        <h1 className="home-heading">
          Choose Your <em>Arena</em>
        </h1>

        <p className="home-sub">
          Rankings, rosters, and match history for CSU&apos;s competitive
          esports program.
        </p>

        <div className="home-cascade">
          {activeGames.map((g) => (
            <GameCard key={g.slug} g={g} onClick={() => router.push(g.href)} />
          ))}
          <div className="home-cascade-break" aria-hidden="true" />
          {comingSoonGames.map((g) => (
            <GameCard key={g.slug} g={g} />
          ))}
        </div>
      </div>
    </main>
  );
}
