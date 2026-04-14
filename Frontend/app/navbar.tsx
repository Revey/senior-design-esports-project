"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";

const navItems = [
  { label: "Leagues", href: "/leagues" },
  { label: "Tournaments", href: "/tournaments" },
  { label: "Teams", href: "/teams" },
  { label: "Players", href: "/players" },
  { label: "About", href: "/about" },
  { label: "Connect Riot", href: "/valorant/auth" },
];

export default function Navbar() {
  const headerRef = useRef<HTMLElement>(null);
  const lastScrollY = useRef(0);
  const pathname = usePathname();

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;

    const handleScroll = () => {
      const currentScrollY = window.scrollY;

      if (currentScrollY < 60) {
        header.classList.remove("navbar-hidden");
      } else if (currentScrollY > lastScrollY.current) {
        // Scrolling down — hide
        header.classList.add("navbar-hidden");
      } else {
        // Scrolling up — show
        header.classList.remove("navbar-hidden");
      }

      lastScrollY.current = currentScrollY;
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header ref={headerRef} className="site-navbar">
      {/* Logo — pinned to the left */}
      <Link href="/" className="navbar-logo-link" aria-label="Home">
        <Image
          src="/images/collegerankericonwhite.png"
          alt="CollegeEsportsTracker logo"
          width={38}
          height={38}
          priority
        />
      </Link>

      {/* Nav links — absolutely centered in the bar */}
      <nav className="navbar-links" aria-label="Main navigation">
        {navItems.map((item) => {
          const isActive = item.href !== "/" && pathname.startsWith(item.href);
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`navbar-link${isActive ? " navbar-link--active" : ""}`}
              aria-current={isActive ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}