"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminFetch, API_BASE, getToken } from "../adminClient";

type Match = {
  _id: string;
  game: string;
  team1Name?: string;
  team2Name?: string;
  team1Score: number;
  team2Score: number;
  format?: string;
  date?: string;
};

type MatchListResp = {
  items: Match[];
  total: number;
  page: number;
  limit: number;
};

export default function AdminMatchesPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editScores, setEditScores] = useState<{ t1: string; t2: string }>({ t1: "", t2: "" });

  useEffect(() => {
    if (!getToken()) {
      router.replace("/admin/login");
      return;
    }
    adminFetch("/api/admin/me")
      .then(() => setReady(true))
      .catch(() => router.replace("/admin/login"));
  }, [router]);

  async function refresh() {
    try {
      setError(null);
      const res = await fetch(`${API_BASE}/api/matches/?limit=50`);
      if (!res.ok) throw new Error(`Failed to load (${res.status})`);
      const data = (await res.json()) as MatchListResp;
      setMatches(data.items);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    if (ready) refresh();
  }, [ready]);

  async function handleSave(id: string) {
    const t1 = Number(editScores.t1);
    const t2 = Number(editScores.t2);
    if (!Number.isFinite(t1) || !Number.isFinite(t2)) {
      setError("Scores must be numbers");
      return;
    }
    try {
      await adminFetch(`/api/admin/matches/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ team1Score: t1, team2Score: t2 }),
      });
      setEditing(null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this match? This will reverse the W/L update and remove all player stat rows.")) {
      return;
    }
    try {
      await adminFetch(`/api/admin/matches/${id}`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <Link href="/admin" className="text-sm text-white/60 hover:text-white">
          ← Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mt-3 mb-6">Manage Matches</h1>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        <div className="rounded-xl border border-white/10 bg-white/5 overflow-hidden">
          <div className="grid grid-cols-[1fr_80px_2fr_120px_140px] gap-3 px-4 py-3 text-xs uppercase tracking-wider text-white/50 border-b border-white/10">
            <div>Date</div>
            <div>Game</div>
            <div>Matchup</div>
            <div className="text-right">Score</div>
            <div className="text-right">Actions</div>
          </div>
          {matches.length === 0 && (
            <p className="px-4 py-6 text-white/40 text-sm">No matches found.</p>
          )}
          {matches.map((m) => {
            const isEditing = editing === m._id;
            return (
              <div
                key={m._id}
                className="grid grid-cols-[1fr_80px_2fr_120px_140px] gap-3 px-4 py-3 text-sm items-center border-b border-white/5"
              >
                <div className="text-white/70">
                  {m.date ? new Date(m.date).toLocaleDateString() : "—"}
                </div>
                <div>
                  <span
                    className={
                      m.game === "valorant"
                        ? "px-2 py-0.5 rounded text-xs font-semibold bg-[#ff465526] text-[#ff4655]"
                        : "px-2 py-0.5 rounded text-xs font-semibold bg-[#c89b3c26] text-[#c89b3c]"
                    }
                  >
                    {m.game === "valorant" ? "VAL" : "LoL"}
                  </span>
                </div>
                <div>
                  <span className="font-medium">{m.team1Name}</span>
                  <span className="text-white/40 mx-2">vs</span>
                  <span className="font-medium">{m.team2Name}</span>
                </div>
                <div className="text-right tabular-nums">
                  {isEditing ? (
                    <div className="flex gap-1 justify-end">
                      <input
                        type="number"
                        value={editScores.t1}
                        onChange={(e) => setEditScores((s) => ({ ...s, t1: e.target.value }))}
                        className="w-12 bg-black border border-white/20 rounded px-1 py-0.5 text-right"
                      />
                      <span className="text-white/40">-</span>
                      <input
                        type="number"
                        value={editScores.t2}
                        onChange={(e) => setEditScores((s) => ({ ...s, t2: e.target.value }))}
                        className="w-12 bg-black border border-white/20 rounded px-1 py-0.5 text-right"
                      />
                    </div>
                  ) : (
                    <span>
                      {m.team1Score}–{m.team2Score}
                    </span>
                  )}
                </div>
                <div className="flex gap-2 justify-end">
                  {isEditing ? (
                    <>
                      <button
                        onClick={() => handleSave(m._id)}
                        className="text-xs px-2 py-1 rounded bg-green-600/30 text-green-400 hover:bg-green-600/50"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditing(null)}
                        className="text-xs px-2 py-1 rounded bg-white/10 text-white/70 hover:bg-white/20"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => {
                          setEditing(m._id);
                          setEditScores({ t1: String(m.team1Score), t2: String(m.team2Score) });
                        }}
                        className="text-xs px-2 py-1 rounded bg-white/10 text-white/80 hover:bg-white/20"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(m._id)}
                        className="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/40"
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
