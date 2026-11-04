"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, X } from "lucide-react";
import { api, dateLabel, Post, statusLabel } from "@/lib/api";
import { ErrorNotice, PageHeading } from "@/components/common";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
export default function Calendar() {
  const [anchor, setAnchor] = useState(() => new Date());
  const [weekly, setWeekly] = useState(false);
  const [selected, setSelected] = useState<Post | null>(null);
  const start = new Date(
    anchor.getFullYear(),
    anchor.getMonth(),
    weekly ? anchor.getDate() : 1,
  );
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  const end = new Date(start);
  end.setDate(end.getDate() + (weekly ? 7 : 42));
  const posts = useQuery({
    queryKey: ["calendar", start.toISOString(), end.toISOString()],
    queryFn: () =>
      api<Post[]>(
        `/calendar?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`,
      ),
    refetchInterval: 30000,
  });
  const days = Array.from({ length: weekly ? 7 : 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
  function move(direction: number) {
    const d = new Date(anchor);
    if (weekly) d.setDate(d.getDate() + direction * 7);
    else d.setMonth(d.getMonth() + direction, 1);
    setAnchor(d);
  }
  return (
    <>
      <PageHeading
        title="A bigger picture."
        subtitle="Plan your rhythm. Calendar times follow your device’s timezone."
      >
        <Button asChild>
          <Link href="/create">
            <Plus size={16} />
            Create post
          </Link>
        </Button>
      </PageHeading>
      <ErrorNotice error={posts.error} />
      <section className="panel">
        <div className="panel-head">
          <div className="row">
            <Button
              variant="ghost"
              size="sm"
              aria-label="Previous period"
              onClick={() => move(-1)}
            >
              <ChevronLeft size={17} />
            </Button>
            <h2>
              {anchor.toLocaleDateString(undefined, {
                month: "long",
                year: "numeric",
              })}
            </h2>
            <Button
              variant="ghost"
              size="sm"
              aria-label="Next period"
              onClick={() => move(1)}
            >
              <ChevronRight size={17} />
            </Button>
          </div>
          <div className="row">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAnchor(new Date())}
            >
              Today
            </Button>
            <select
              aria-label="Calendar view"
              value={weekly ? "week" : "month"}
              onChange={(e) => setWeekly(e.target.value === "week")}
            >
              <option value="month">Month</option>
              <option value="week">Week</option>
            </select>
          </div>
        </div>
        {posts.isPending && (
          <div role="status" className="subtle" style={{ padding: 10 }}>
            Loading calendar…
          </div>
        )}
        <div className="calendar-grid">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <div className="calendar-label" key={d}>
              {d}
            </div>
          ))}
          {days.map((day) => (
            <div
              key={day.toISOString()}
              className={`calendar-day ${day.getMonth() !== anchor.getMonth() ? "dim" : ""} ${day.toDateString() === new Date().toDateString() ? "today" : ""}`}
            >
              <span>{day.getDate()}</span>
              {posts.data?.flatMap((p) =>
                p.targets
                  .filter(
                    (t) =>
                      t.scheduled_at &&
                      new Date(t.scheduled_at).toDateString() ===
                        day.toDateString(),
                  )
                  .map((t) => (
                    <button
                      key={t.id}
                      className={`calendar-event ${t.status}`}
                      onClick={() => setSelected(p)}
                      title={`${t.username}: ${statusLabel(t.status)}`}
                    >
                      {new Date(t.scheduled_at!).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}{" "}
                      · {t.username}
                    </button>
                  )),
              )}
            </div>
          ))}
        </div>
      </section>
      <div className="row subtle" style={{ marginTop: 20 }}>
        <span className="badge scheduled">Scheduled</span>
        <span className="badge published">Published</span>
        <span className="badge failed">Failed</span>
      </div>
      {selected && (
        <Dialog label="Scheduled post" onClose={() => setSelected(null)}>
          <section className="panel" onClick={(e) => e.stopPropagation()}>
            <div className="panel-head">
              <h2>Post details</h2>
              <Button
                variant="ghost"
                size="sm"
                aria-label="Close details"
                onClick={() => setSelected(null)}
                autoFocus
              >
                <X size={18} />
              </Button>
            </div>
            <div className="panel-body">
              <h3>{selected.caption || "Video post"}</h3>
              {selected.targets.map((t) => (
                <div key={t.id} style={{ margin: "20px 0" }}>
                  <div className="row spread">
                    <strong>{t.username}</strong>
                    <span className={`badge ${t.status}`}>
                      {statusLabel(t.status)}
                    </span>
                  </div>
                  <p>
                    {dateLabel(t.scheduled_at)} · {statusLabel(t.format)}
                  </p>
                  {t.error && <p className="error">{t.error}</p>}
                </div>
              ))}
              <Button asChild variant="outline">
                <Link href="/scheduled">Manage posts</Link>
              </Button>
            </div>
          </section>
        </Dialog>
      )}
    </>
  );
}
