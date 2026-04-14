"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminFetch, clearToken, getToken } from "./adminClient";

export default function AdminHome() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }
    adminFetch("/api/admin/me")
      .then(() => setReady(true))
      .catch(() => router.replace("/admin/login"));
  }, [router]);

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <button
            onClick={() => {
              clearToken();
              router.push("/admin/login");
            }}
            className="text-sm text-white/60 hover:text-white"
          >
            Sign out
          </button>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Link
            href="/admin/match"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Enter Match</div>
            <div className="text-sm text-white/60 mt-1">
              Upload post-game stats for Valorant or League of Legends.
            </div>
          </Link>
          <Link
            href="/admin/players"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Manage Players</div>
            <div className="text-sm text-white/60 mt-1">
              Create, link, and unlink players from teams.
            </div>
          </Link>
          <Link
            href="/admin/teams"
            className="p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition"
          >
            <div className="text-lg font-semibold">Manage Teams</div>
            <div className="text-sm text-white/60 mt-1">
              View teams, their records, and rosters by school.
            </div>
          </Link>
        </div>
      </div>
    </main>
  );
}
