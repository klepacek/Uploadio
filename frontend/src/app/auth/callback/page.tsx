"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
export default function Callback() {
  const [error, setError] = useState("");
  useEffect(() => {
    async function exchange() {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      if (!code)
        throw new Error(
          "Verification link is invalid or expired. Request a new link.",
        );
      const { error } = await supabase().auth.exchangeCodeForSession(code);
      if (error) throw error;
      window.location.replace(
        params.get("next") === "reset" ? "/reset-password" : "/dashboard",
      );
    }
    exchange().catch((e) =>
      setError(e instanceof Error ? e.message : "Verification failed"),
    );
  }, []);
  return (
    <main className="loading">
      {error || "Verifying your account…"}
      {error && (
        <p>
          <Link href="/login">Return to log in</Link>
        </p>
      )}
    </main>
  );
}
