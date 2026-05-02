"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  adminFetch,
  getToken,
  type ConfKind,
  type Conference,
  type Game,
  type LeagueTreeOrg,
  type Organization,
  type Season,
  type Semester,
} from "../adminClient";

export default function LeaguesAdmin() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tree, setTree] = useState<LeagueTreeOrg[]>([]);
  const [showCreateOrg, setShowCreateOrg] = useState(false);

  useEffect(() => {
    if (!getToken()) router.replace("/admin/login");
    else setReady(true);
  }, [router]);

  const reload = useCallback(async () => {
    const data = await adminFetch<LeagueTreeOrg[]>(`/api/admin/leagues-tree`);
    setTree(data);
  }, []);

  useEffect(() => {
    if (ready) reload();
  }, [ready, reload]);

  if (!ready) return null;

  return (
    <main className="min-h-screen bg-black text-white px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <Link href="/admin" className="text-sm text-white/60 hover:text-white">
          ← Back
        </Link>
        <div className="flex items-center justify-between mt-2 mb-2 gap-4 flex-wrap">
          <h1 className="text-2xl font-bold">Leagues</h1>
          <button
            onClick={() => setShowCreateOrg(true)}
            className="px-4 py-2 rounded bg-white text-black text-sm font-semibold hover:bg-white/90"
          >
            + Create Organization
          </button>
        </div>
        <p className="text-white/50 text-sm mb-6">
          Organize by <strong>Organization</strong> (CVAL, NECC, NACE…),{" "}
          <strong>Season</strong> (Fall 2025, Spring 2026…), and{" "}
          <strong>Conference / Division</strong>.
        </p>

        <div className="space-y-3">
          {tree.map((o) => (
            <OrgCard key={o._id} org={o} onChanged={reload} />
          ))}
          {tree.length === 0 && (
            <p className="text-white/50 text-sm">
              No organizations yet — create one to get started.
            </p>
          )}
        </div>
      </div>

      {showCreateOrg && (
        <CreateOrgModal
          onClose={() => setShowCreateOrg(false)}
          onCreated={() => {
            setShowCreateOrg(false);
            reload();
          }}
        />
      )}
    </main>
  );
}

// ---------- org card ----------

function OrgCard({
  org,
  onChanged,
}: {
  org: LeagueTreeOrg;
  onChanged: () => void | Promise<void>;
}) {
  const [expanded, setExpanded] = useState(true);
  const [showSeason, setShowSeason] = useState(false);
  const [showConf, setShowConf] = useState(false);

  async function deleteOrg() {
    if (
      !confirm(
        `Delete ${org.abbreviation} and all its seasons, conferences, and memberships? This cannot be undone.`,
      )
    )
      return;
    await adminFetch(`/api/admin/orgs/${org._id}`, { method: "DELETE" });
    await onChanged();
  }

  async function toggleSeasonActive(s: Season) {
    await adminFetch(`/api/admin/seasons/${s._id}`, {
      method: "PATCH",
      body: JSON.stringify({ active: !s.active }),
    });
    await onChanged();
  }

  async function deleteSeason(s: Season) {
    if (!confirm(`Delete season "${s.label}"?`)) return;
    await adminFetch(`/api/admin/seasons/${s._id}`, { method: "DELETE" });
    await onChanged();
  }

  async function deleteConference(c: Conference) {
    if (
      !confirm(
        `Delete conference "${c.name}"? Team memberships in this conference will be removed.`,
      )
    )
      return;
    await adminFetch(`/api/admin/conferences/${c._id}`, { method: "DELETE" });
    await onChanged();
  }

  // Group conferences by tier (NACE: Premier/Plus; everyone else: untiered).
  const byTier = new Map<string, Conference[]>();
  for (const c of org.conferences) {
    const key = c.tier || "";
    if (!byTier.has(key)) byTier.set(key, []);
    byTier.get(key)!.push(c);
  }
  const tierKeys = Array.from(byTier.keys()).sort();

  return (
    <div className="rounded-lg border border-white/10 bg-white/5 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-3 text-left"
        >
          <span className="text-white/40 text-sm">{expanded ? "▼" : "▶"}</span>
          <span className="font-semibold">{org.abbreviation}</span>
          <span className="text-white/50 text-sm">{org.name}</span>
          <span className="text-xs text-white/40">
            {org.games.map((g) => (g === "valorant" ? "VAL" : "LoL")).join(" · ")}
          </span>
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">
            {org.seasons.length} seasons · {org.conferences.length} conferences
          </span>
          <button
            onClick={deleteOrg}
            className="text-xs px-2 py-1 rounded bg-red-600/20 text-red-400 hover:bg-red-600/40"
          >
            Delete
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10 px-4 py-4 grid md:grid-cols-2 gap-6">
          {/* Seasons */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs uppercase tracking-wider text-white/50">
                Seasons
              </h3>
              <button
                onClick={() => setShowSeason(true)}
                className="text-xs text-emerald-400 hover:text-emerald-300"
              >
                + Add season
              </button>
            </div>
            {org.seasons.length === 0 && (
              <p className="text-xs text-white/40">No seasons yet.</p>
            )}
            <ul className="space-y-1">
              {org.seasons.map((s) => (
                <li
                  key={s._id}
                  className="flex items-center gap-2 text-sm py-1"
                >
                  <span className="font-medium">{s.label}</span>
                  <span className="text-xs text-white/40">({s.year})</span>
                  <button
                    onClick={() => toggleSeasonActive(s)}
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      s.active
                        ? "bg-emerald-500/30 text-emerald-300"
                        : "bg-white/10 text-white/50 hover:bg-white/20"
                    }`}
                    title={s.active ? "Active — click to deactivate" : "Set active"}
                  >
                    {s.active ? "active" : "inactive"}
                  </button>
                  <button
                    onClick={() => deleteSeason(s)}
                    className="ml-auto text-xs text-red-400 hover:text-red-300"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {/* Conferences */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs uppercase tracking-wider text-white/50">
                Conferences / Divisions
              </h3>
              <button
                onClick={() => setShowConf(true)}
                className="text-xs text-emerald-400 hover:text-emerald-300"
              >
                + Add conference
              </button>
            </div>
            {org.conferences.length === 0 && (
              <p className="text-xs text-white/40">No conferences yet.</p>
            )}
            <div className="space-y-3">
              {tierKeys.map((tier) => (
                <div key={tier}>
                  {tier && (
                    <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">
                      {tier}
                    </div>
                  )}
                  <ul className="space-y-1">
                    {byTier.get(tier)!.map((c) => (
                      <li
                        key={c._id}
                        className="flex items-center gap-2 text-sm py-1"
                      >
                        <span className="font-medium">{c.name}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-white/10 text-white/50">
                          {c.kind}
                        </span>
                        <button
                          onClick={() => deleteConference(c)}
                          className="ml-auto text-xs text-red-400 hover:text-red-300"
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {showSeason && (
        <AddSeasonModal
          org={org}
          onClose={() => setShowSeason(false)}
          onCreated={async () => {
            setShowSeason(false);
            await onChanged();
          }}
        />
      )}
      {showConf && (
        <AddConferenceModal
          org={org}
          onClose={() => setShowConf(false)}
          onCreated={async () => {
            setShowConf(false);
            await onChanged();
          }}
        />
      )}
    </div>
  );
}

// ---------- modals ----------

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-30 bg-black/70 flex items-start justify-center overflow-y-auto py-10 px-4">
      <div className="w-full max-w-md rounded-lg border border-white/15 bg-neutral-900 p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="text-white/60 hover:text-white text-2xl leading-none"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function CreateOrgModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [abbr, setAbbr] = useState("");
  const [games, setGames] = useState<Game[]>(["valorant"]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  function toggleGame(g: Game) {
    setGames((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g],
    );
  }

  async function submit() {
    setErr("");
    if (!name.trim() || !abbr.trim()) {
      setErr("Name and abbreviation required.");
      return;
    }
    setSubmitting(true);
    try {
      await adminFetch<Organization>(`/api/admin/orgs`, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), abbreviation: abbr.trim(), games }),
      });
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ModalShell title="Create Organization" onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-white/50 mb-1">Name *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Collegiate Valorant"
            className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
          />
        </div>
        <div>
          <label className="block text-xs text-white/50 mb-1">
            Abbreviation *
          </label>
          <input
            value={abbr}
            onChange={(e) => setAbbr(e.target.value.toUpperCase())}
            placeholder="e.g. CVAL"
            className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
          />
        </div>
        <div>
          <label className="block text-xs text-white/50 mb-2">Games</label>
          <div className="flex gap-2">
            {(["valorant", "lol"] as Game[]).map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => toggleGame(g)}
                className={`px-3 py-1.5 rounded text-sm border ${
                  games.includes(g)
                    ? "bg-white text-black border-white"
                    : "border-white/20 text-white/70 hover:bg-white/5"
                }`}
              >
                {g === "valorant" ? "VAL" : "LoL"}
              </button>
            ))}
          </div>
        </div>
        {err && <p className="text-sm text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded border border-white/20 text-sm hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-4 py-2 rounded bg-white text-black text-sm font-semibold hover:bg-white/90 disabled:opacity-40"
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

function AddSeasonModal({
  org,
  onClose,
  onCreated,
}: {
  org: Organization;
  onClose: () => void;
  onCreated: () => void;
}) {
  const now = new Date();
  const fallYear = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  const defaultYear = `${fallYear}-${fallYear + 1}`;
  const [year, setYear] = useState(defaultYear);
  const [semester, setSemester] = useState<Semester>("Fall");
  const [active, setActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    setErr("");
    if (!/^\d{4}-\d{4}$/.test(year)) {
      setErr("Year must be like 2025-2026.");
      return;
    }
    setSubmitting(true);
    try {
      await adminFetch(`/api/admin/seasons`, {
        method: "POST",
        body: JSON.stringify({ orgId: org._id, year, semester, active }),
      });
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ModalShell title={`Add season — ${org.abbreviation}`} onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-white/50 mb-1">
            Academic year *
          </label>
          <input
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="2025-2026"
            className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
          />
        </div>
        <div>
          <label className="block text-xs text-white/50 mb-1">Semester *</label>
          <select
            value={semester}
            onChange={(e) => setSemester(e.target.value as Semester)}
            className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
          >
            <option value="fall">Fall</option>
            <option value="spring">Spring</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
          />
          Mark as active (deactivates other seasons for this org)
        </label>
        {err && <p className="text-sm text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded border border-white/20 text-sm hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-4 py-2 rounded bg-white text-black text-sm font-semibold hover:bg-white/90 disabled:opacity-40"
          >
            {submitting ? "Adding…" : "Add season"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

function AddConferenceModal({
  org,
  onClose,
  onCreated,
}: {
  org: Organization;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [tier, setTier] = useState("");
  const [kind, setKind] = useState<ConfKind>("regional");
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkTier, setBulkTier] = useState("");
  const [bulkCount, setBulkCount] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    setErr("");
    setSubmitting(true);
    try {
      if (bulkMode) {
        for (let i = 1; i <= bulkCount; i++) {
          await adminFetch(`/api/admin/conferences`, {
            method: "POST",
            body: JSON.stringify({
              orgId: org._id,
              name: `Division ${i}`,
              tier: bulkTier.trim() || null,
              kind: "division",
            }),
          });
        }
      } else {
        if (!name.trim()) {
          setErr("Name required.");
          setSubmitting(false);
          return;
        }
        await adminFetch(`/api/admin/conferences`, {
          method: "POST",
          body: JSON.stringify({
            orgId: org._id,
            name: name.trim(),
            tier: tier.trim() || null,
            kind,
          }),
        });
      }
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ModalShell title={`Add conference — ${org.abbreviation}`} onClose={onClose}>
      <div className="space-y-3">
        <div className="flex gap-2 text-sm">
          <button
            type="button"
            onClick={() => setBulkMode(false)}
            className={`flex-1 px-3 py-1.5 rounded border ${
              !bulkMode
                ? "bg-white text-black border-white"
                : "border-white/20 text-white/70"
            }`}
          >
            Single
          </button>
          <button
            type="button"
            onClick={() => setBulkMode(true)}
            className={`flex-1 px-3 py-1.5 rounded border ${
              bulkMode
                ? "bg-white text-black border-white"
                : "border-white/20 text-white/70"
            }`}
          >
            Bulk divisions (1–N)
          </button>
        </div>

        {!bulkMode && (
          <>
            <div>
              <label className="block text-xs text-white/50 mb-1">Name *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Midwest, Division 2, Premier Division 1"
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              />
            </div>
            <div>
              <label className="block text-xs text-white/50 mb-1">
                Tier (optional — e.g. Premier, Plus)
              </label>
              <input
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                placeholder="Used by NACE to group divisions"
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              />
            </div>
            <div>
              <label className="block text-xs text-white/50 mb-1">Kind</label>
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as ConfKind)}
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              >
                <option value="regional">Regional (e.g. Midwest)</option>
                <option value="division">Division (skill-based)</option>
                <option value="partner">Partner (e.g. CVAL-NECC)</option>
                <option value="tier">Tier (e.g. Premier)</option>
              </select>
            </div>
          </>
        )}

        {bulkMode && (
          <>
            <p className="text-xs text-white/50">
              Creates <strong>Division 1</strong> through <strong>Division N</strong>{" "}
              under the given tier label. Use this for NECC (no tier) or NACE
              (tier = Premier / Plus).
            </p>
            <div>
              <label className="block text-xs text-white/50 mb-1">
                Tier (optional)
              </label>
              <input
                value={bulkTier}
                onChange={(e) => setBulkTier(e.target.value)}
                placeholder="e.g. Premier (leave blank for NECC)"
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              />
            </div>
            <div>
              <label className="block text-xs text-white/50 mb-1">
                Number of divisions
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={bulkCount}
                onChange={(e) =>
                  setBulkCount(Math.max(1, Math.min(20, Number(e.target.value))))
                }
                className="w-full px-3 py-2 rounded bg-black/40 border border-white/20"
              />
            </div>
          </>
        )}

        {err && <p className="text-sm text-red-400">{err}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded border border-white/20 text-sm hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-4 py-2 rounded bg-white text-black text-sm font-semibold hover:bg-white/90 disabled:opacity-40"
          >
            {submitting ? "Adding…" : "Add"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
