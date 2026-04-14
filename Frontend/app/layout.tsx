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
    default: "CollegeRankers — CSU Esports Hub",
    template: "%s | CollegeRankers",
  },
  description: "Collegiate esports stats for Cleveland State University. Track Valorant and League of Legends teams, players, and tournament results.",
  openGraph: {
    title: "CollegeRankers — CSU Esports Hub",
    description: "Collegiate esports stats for Cleveland State University.",
    siteName: "CollegeRankers",
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