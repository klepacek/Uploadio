"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CircleHelp,
  Clock3,
  FileVideo,
  History,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu,
  Plus,
  Settings2,
  Upload,
} from "lucide-react";
import { Brand } from "./brand";
import { supabase } from "@/lib/supabase";
const links = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/create", label: "Create post", icon: Plus },
  { href: "/drafts", label: "Drafts", icon: FileVideo },
  { href: "/scheduled", label: "Scheduled", icon: Clock3 },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/history", label: "Publishing history", icon: History },
  { href: "/media", label: "Media library", icon: Upload },
];
export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queries = useQueryClient();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    try {
      const auth = supabase().auth;
      auth
        .getSession()
        .then(({ data, error }) => {
          if (error) throw error;
          if (!data.session) router.replace("/login");
          else setReady(true);
        })
        .catch((error) =>
          setError(
            error instanceof Error
              ? error.message
              : "Authentication unavailable",
          ),
        );
      const { data } = auth.onAuthStateChange((event) => {
        if (event === "SIGNED_OUT") {
          queries.clear();
          router.replace("/login");
        }
      });
      return () => data.subscription.unsubscribe();
    } catch (e) {
      Promise.reject(e).catch((error) =>
        setError(
          error instanceof Error ? error.message : "Authentication unavailable",
        ),
      );
    }
  }, [router, queries]);
  if (error)
    return (
      <main className="content">
        <Brand />
        <div className="error" style={{ marginTop: 30 }}>
          {error}
        </div>
        <Link href="/">Return home</Link>
      </main>
    );
  if (!ready) return <div className="loading">Opening your workspace…</div>;
  const current = [
    ...links,
    { href: "/accounts", label: "Connected accounts" },
    { href: "/settings", label: "Settings" },
  ].find((link) => pathname === link.href)?.label;
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <Brand />
        <div className="workspace-label">
          <span>Workspace</span>Personal workspace
        </div>
        <div className="nav-label">Publishing</div>
        <nav aria-label="Main navigation">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              onClick={() => setOpen(false)}
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className={`nav-link ${pathname === href ? "active" : ""}`}
            >
              <Icon size={17} />
              {label}
            </Link>
          ))}
          <div className="nav-label">Manage</div>
          <Link
            onClick={() => setOpen(false)}
            href="/accounts"
            className={`nav-link ${pathname === "/accounts" ? "active" : ""}`}
          >
            <Link2 size={17} />
            Connected accounts
          </Link>
          <Link
            onClick={() => setOpen(false)}
            href="/settings"
            className={`nav-link ${pathname === "/settings" ? "active" : ""}`}
          >
            <Settings2 size={17} />
            Settings
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <a
            href="https://github.com/klepacek/Uploadio#readme"
            className="nav-link"
          >
            <CircleHelp size={17} />
            Help & documentation
          </a>
          <button
            className="nav-link"
            style={{ width: "100%", border: 0, background: "transparent" }}
            onClick={async () => {
              const { error } = await supabase().auth.signOut();
              if (error) setError(error.message);
            }}
          >
            <LogOut size={17} />
            Log out
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="row">
            <button
              className="mobile-menu"
              aria-label={open ? "Close navigation" : "Open navigation"}
              onClick={() => setOpen(!open)}
            >
              <Menu size={20} />
            </button>
            <span>
              Workspace{" "}
              <span style={{ margin: "0 12px", color: "#505555" }}>/</span>{" "}
              <span className="crumb">{current}</span>
            </span>
          </div>
          <div className="row">
            <span>Personal workspace</span>
            <div className="avatar">U</div>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
