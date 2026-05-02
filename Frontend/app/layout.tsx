import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Navbar from "./navbar";
import Footer from "./footer";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Campus Rankers — Collegiate Esports Stats",
    template: "%s | Campus Rankers",
  },
  description: "Collegiate Valorant and League of Legends — rankings, rosters, match history, and per-player stats across CVAL, CLOL, NACE, and more.",
  openGraph: {
    title: "Campus Rankers — Collegiate Esports Stats",
    description: "Collegiate Valorant and League of Legends — rankings, rosters, match history, and per-player stats.",
    siteName: "Campus Rankers",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Navbar />
        {children}
        <Footer />
      </body>
    </html>
  );
}