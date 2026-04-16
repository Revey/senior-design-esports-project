"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE, setToken } from "../adminClient";

export default function AdminLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Invalid password");
      }
      const data = (await res.json()) as { token: string };
      setToken(data.token);
      const returnTo = typeof window !== "undefined"
        ? sessionStorage.getItem("admin_return") || "/admin"
        : "/admin";
      if (typeof window !== "undefined") sessionStorage.removeItem("admin_return");
      router.push(returnTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-black text-white px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 p-6 border border-white/10 rounded-xl bg-white/5"
      >
        <h1 className="text-xl font-semibold">Admin Login</h1>
        <input
          type="password"
          autoFocus
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 rounded bg-black/40 border border-white/20 outline-none focus:border-white/50"
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          disabled={loading || !password}
          className="w-full py-2 rounded bg-white text-black font-medium disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
