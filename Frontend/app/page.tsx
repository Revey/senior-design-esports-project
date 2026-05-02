"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

const GAMES = [
  {
    slug: "valorant",
    name: "Valorant",
    tag: "CVAL · 5v5 tactical",
    href: "/valorant",
    image: "/images/valorantimage.png",
    modifier: "val" as const,
  },
  {
    slug: "league",
    name: "League of Legends",
    tag: "CLOL · 5v5 MOBA",
    href: "/league",
    image: "/images/league-of-legends.png",
    modifier: "lol" as const,
  },
];

function ArrowIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
          Choose your <em>arena</em>.
        </h1>

        <p className="home-sub">
          Rankings, rosters, and match history for collegiate Valorant and
          League of Legends programs — updated after every matchday.
        </p>

        <div className="home-cascade">
          {GAMES.map((g) => (
            <button
              key={g.slug}
              type="button"
              className={`game-card game-card--${g.modifier}`}
              onClick={() => router.push(g.href)}
              aria-label={`Open ${g.name} stats`}
            >
              <div className="game-shell">
                <div className="game-core">
                  <div className="game-image-wrap">
                    <Image
                      src={g.image}
                      alt={`${g.name} artwork`}
                      fill
                      sizes="(max-width: 768px) 320px, 320px"
                      style={{ objectFit: "contain" }}
                      priority={g.modifier === "val"}
                    />
                  </div>

                  <div className="game-meta">
                    <div className="game-name">{g.name}</div>
                    <div className="game-tag">{g.tag}</div>
                  </div>

                  <div className="game-cta">
                    <span>Enter rankings</span>
                    <span className="game-cta-icon" aria-hidden="true">
                      <ArrowIcon />
                    </span>
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </main>
  );
}
