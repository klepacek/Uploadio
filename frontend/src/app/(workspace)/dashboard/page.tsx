"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCheck,
  CircleAlert,
  Clock3,
  Link2,
  Plus,
} from "lucide-react";
import { api, dateLabel, Post, statusLabel } from "@/lib/api";
import { PageHeading, Empty, ErrorNotice } from "@/components/common";
import { Button } from "@/components/ui/button";
export default function Dashboard() {
  const metrics = useQuery({
    queryKey: ["dashboard"],
    queryFn: () =>
      api<{ connected_accounts: number; targets: Record<string, number> }>(
        "/dashboard",
      ),
  });
  const posts = useQuery({
    queryKey: ["posts"],
    queryFn: () => api<Post[]>("/posts"),
    refetchInterval: 30000,
  });
  const counts = metrics.data?.targets;
  const upcoming = posts.data
    ?.flatMap((p) =>
      p.targets
        .filter((t) => ["scheduled", "queued", "retry"].includes(t.status))
        .map((t) => ({ ...t, post: p })),
    )
    .sort((a, b) => (a.scheduled_at || "").localeCompare(b.scheduled_at || ""));
  const recent = posts.data
    ?.flatMap((p) =>
      p.targets
        .filter((t) =>
          ["published", "failed", "draft_uploaded", "uncertain"].includes(
            t.status,
          ),
        )
        .map((t) => ({ ...t, post: p })),
    )
    .slice(0, 5);
  return (
    <>
      <PageHeading
        title="A little overview."
        subtitle="Your content, your channels, and what’s coming next."
      >
        <Button asChild>
          <Link href="/create">
            <Plus size={16} />
            Create post
          </Link>
        </Button>
      </PageHeading>
      <ErrorNotice error={metrics.error || posts.error} />
      <div className="grid metrics">
        {[
          {
            label: "Connected accounts",
            value: metrics.data?.connected_accounts,
            icon: Link2,
            foot: "Your publishing destinations",
          },
          {
            label: "Scheduled posts",
            value:
              counts &&
              (counts.scheduled || 0) +
                (counts.queued || 0) +
                (counts.retry || 0),
            icon: Clock3,
            foot: "Ready for their moment",
          },
          {
            label: "Published",
            value: counts?.published ?? (counts ? 0 : undefined),
            icon: CheckCheck,
            foot: "Successfully published destinations",
          },
          {
            label: "Needs attention",
            value: counts && (counts.failed || 0) + (counts.uncertain || 0),
            icon: CircleAlert,
            foot: "Destinations to review",
          },
        ].map(({ label, value, icon: Icon, foot }) => (
          <article key={label} className="metric">
            <div className="metric-head">
              {label}
              <Icon size={16} />
            </div>
            <div className="metric-value">{value ?? "—"}</div>
            <div className="metric-foot">{foot}</div>
          </article>
        ))}
      </div>
      <div className="grid dashboard-columns">
        <section className="panel">
          <div className="panel-head">
            <h2>Coming up next</h2>
            <Link className="row subtle" href="/calendar">
              View calendar <ArrowRight size={14} />
            </Link>
          </div>
          {posts.isPending ? (
            <div className="loading">Loading scheduled content…</div>
          ) : upcoming?.length ? (
            upcoming.slice(0, 6).map((t) => (
              <Link href="/scheduled" key={t.id} className="list-item">
                <div>
                  <h3>{t.caption || t.post.caption || "Untitled video"}</h3>
                  <p>
                    {t.username} · {statusLabel(t.format)}
                  </p>
                  <span className="subtle">
                    {dateLabel(t.scheduled_at, t.post.timezone)}
                  </span>
                </div>
                <span className={`badge ${t.status}`}>
                  {statusLabel(t.status)}
                </span>
              </Link>
            ))
          ) : (
            <Empty
              title="Your calendar has room."
              description="Start with a video, choose a destination, and give your next post a time to shine."
            >
              <Button asChild variant="outline">
                <Link href="/create">
                  <Plus size={15} />
                  Create your first post
                </Link>
              </Button>
            </Empty>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Recent activity</h2>
            <Link href="/history" className="subtle">
              View all ↗
            </Link>
          </div>
          {recent?.length ? (
            recent.map((t) => (
              <div key={t.id} className="list-item">
                <div>
                  <h3>{t.username}</h3>
                  <p>{t.caption || t.post.caption || "Video"}</p>
                  <span className={`badge ${t.status}`}>
                    {statusLabel(t.status)}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <Empty
              title="A fresh start."
              description="Publishing results will appear here as your content goes out."
            />
          )}
        </section>
      </div>
      <div className="note" style={{ marginTop: 25 }}>
        A destination is tracked separately for every account. TikTok inbox
        uploads need to be finished in TikTok and are never counted as
        published.
      </div>
    </>
  );
}
