"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// Legacy `/valorant/stats?team=<slug>` route — was a hardcoded CSU-era
// per-player stats page with no DB backing. Real stats now live at
// /teams/{slug} (Postgres-backed). Redirect there, preserving any team slug
// passed in the query string.

function RedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  useEffect(() => {
    const team = searchParams?.get("team");
    if (team) {
      router.replace(`/teams/${team}`);
    } else {
      router.replace("/teams?game=Valorant");
    }
  }, [router, searchParams]);
  return null;
}

export default function ValorantStatsRedirect() {
  return (
    <Suspense fallback={null}>
      <RedirectInner />
    </Suspense>
  );
}
