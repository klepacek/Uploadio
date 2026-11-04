import { supabase } from "./supabase";
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase().auth.getSession();
  if (!data.session)
    throw new Error("Your session expired. Please sign in again.");
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}${path}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${data.session.access_token}`,
        ...init.headers,
      },
    },
  );
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Check the form and try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function json(method: string, data?: unknown): RequestInit {
  return {
    method,
    body: data === undefined ? undefined : JSON.stringify(data),
  };
}
export type Account = {
  id: string;
  platform: string;
  username: string;
  status: string;
  scopes: string[];
};
export type Media = {
  id: string;
  filename: string;
  status: string;
  size_bytes: number;
  url: string | null;
  thumbnail_url: string | null;
  metadata: { duration: number; width: number; height: number };
};
export type Target = {
  id: string;
  account_id: string;
  username: string;
  platform: string;
  format: string;
  caption: string;
  settings: Record<string, unknown>;
  status: string;
  scheduled_at: string | null;
  published_at: string | null;
  external_url: string | null;
  error: string | null;
};
export type Post = {
  id: string;
  media_id: string;
  caption: string;
  timezone: string;
  created_at: string;
  targets: Target[];
};
export type Profile = {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
  workspace_id: string;
};
export const statusLabel = (status: string) => status.replaceAll("_", " ");
export function dateLabel(value: string | null, timezone?: string) {
  return value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: timezone,
      }).format(new Date(value))
    : "—";
}
