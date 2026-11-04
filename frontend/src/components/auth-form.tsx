"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowRight } from "lucide-react";
import { Brand } from "./brand";
import { Button } from "./ui/button";
import { supabase } from "@/lib/supabase";
const schema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string(),
});
type Fields = z.infer<typeof schema>;
export function AuthForm({
  mode,
}: {
  mode: "login" | "register" | "forgot-password" | "reset-password";
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });
  const recovery = mode === "forgot-password";
  const reset = mode === "reset-password";
  const title =
    mode === "login"
      ? "Welcome back."
      : mode === "register"
        ? "Make space to create."
        : reset
          ? "Set a new password."
          : "Let’s get you back in.";
  async function submit(values: Fields) {
    setError("");
    setMessage("");
    try {
      const auth = supabase().auth;
      const redirect = `${window.location.origin}/auth/callback`;
      if (!recovery && values.password.length < (mode === "login" ? 1 : 12))
        throw new Error("Use a password with at least 12 characters.");
      const result = recovery
        ? await auth.resetPasswordForEmail(values.email, {
            redirectTo: `${redirect}?next=reset`,
          })
        : reset
          ? await auth.updateUser({ password: values.password })
          : mode === "register"
            ? await auth.signUp({
                ...values,
                options: { emailRedirectTo: redirect },
              })
            : await auth.signInWithPassword(values);
      if (result.error) throw result.error;
      if (recovery)
        setMessage("If an account exists, a recovery email is on its way.");
      else if (mode === "register")
        setMessage("Check your email to verify your account, then sign in.");
      else router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    }
  }
  return (
    <div className="auth-wrap">
      <aside className="auth-story">
        <Brand />
        <div>
          <div className="eyebrow">Your next chapter, scheduled.</div>
          <h1>
            More creating.
            <br />
            Less keeping
            <br />
            track.
          </h1>
          <p>
            A little structure for all the things you want to put out into the
            world.
          </p>
        </div>
        <span className="subtle">Uploadio · A workspace for your content.</span>
      </aside>
      <main className="auth-form">
        <div>
          <div className="eyebrow" style={{ marginBottom: 20 }}>
            Uploadio workspace
          </div>
          <h1>{title}</h1>
          <p style={{ marginBottom: 30 }}>
            {recovery
              ? "We’ll send you a link to reset your password."
              : reset
                ? "Choose a strong password for your account."
                : "Your content, accounts, and next ideas are waiting."}
          </p>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          {message && (
            <div className="success" role="status">
              {message}
            </div>
          )}
          <form onSubmit={handleSubmit(submit)}>
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
              />
              {errors.email && (
                <span className="subtle">{errors.email.message}</span>
              )}
            </div>
            {!recovery && (
              <div className="field">
                <div className="row spread">
                  <label htmlFor="password">Password</label>
                  {mode === "login" && (
                    <Link className="subtle" href="/forgot-password">
                      Forgot password?
                    </Link>
                  )}
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  {...register("password")}
                />
                {mode !== "login" && (
                  <span className="subtle">At least 12 characters.</span>
                )}
              </div>
            )}
            <Button disabled={isSubmitting}>
              {isSubmitting
                ? "Please wait…"
                : recovery
                  ? "Send recovery link"
                  : reset
                    ? "Update password"
                    : mode === "login"
                      ? "Log in"
                      : "Create account"}
              <ArrowRight size={15} />
            </Button>
          </form>
          <div className="auth-footer">
            {mode === "login" ? (
              <>
                New here? <Link href="/register">Create an account</Link>
              </>
            ) : (
              <Link href="/login">Back to log in</Link>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
