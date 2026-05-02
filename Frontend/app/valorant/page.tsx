"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Legacy `/valorant` route — was the original CSU-era team search before
// the Postgres-backed /teams page existed. Now redirects there.
export default function ValorantRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/teams?game=Valorant");
  }, [router]);
  return null;
}
