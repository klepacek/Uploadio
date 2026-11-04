"use client";
import Link from "next/link";
import Image from "next/image";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api, dateLabel, Media, Post, statusLabel } from "@/lib/api";
import { Empty, ErrorNotice, PageHeading } from "./common";
import { Button } from "./ui/button";
export function PostList({
  kind,
}: {
  kind: "drafts" | "scheduled" | "history";
}) {
  const queries = useQueryClient();
  const posts = useQuery({
    queryKey: ["posts"],
    queryFn: () => api<Post[]>("/posts"),
    refetchInterval: 30000,
  });
  const media = useQuery({
    queryKey: ["media"],
    queryFn: () => api<Media[]>("/media"),
  });
  const action = useMutation({
    mutationFn: ({ id, remove }: { id: string; remove?: boolean }) =>
      api(`/posts/${id}${remove ? "" : "/cancel"}`, {
        method: remove ? "DELETE" : "POST",
      }),
    onSuccess: () => {
      queries.invalidateQueries({ queryKey: ["posts"] });
      queries.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const states =
    kind === "drafts"
      ? ["draft", "cancelled"]
      : kind === "scheduled"
        ? ["scheduled", "queued", "retry", "processing"]
        : ["published", "failed", "uncertain", "draft_uploaded"];
  const filtered = posts.data?.filter((p) =>
    p.targets.some((t) => states.includes(t.status)),
  );
  const title =
    kind === "drafts"
      ? "Ideas in progress."
      : kind === "scheduled"
        ? "Coming to a feed near you."
        : "Every destination, accounted for.";
  return (
    <>
      <PageHeading
        title={title}
        subtitle={
          kind === "history"
            ? "Individual results, including partial success and uploads awaiting action."
            : "Keep your content moving at your own pace."
        }
      >
        <Button asChild>
          <Link href="/create">
            <Plus size={16} />
            Create post
          </Link>
        </Button>
      </PageHeading>
      <ErrorNotice error={posts.error || action.error || media.error} />
      <div className="panel">
        {posts.isPending ? (
          <div className="loading">Loading posts…</div>
        ) : filtered?.length ? (
          filtered.map((p) => {
            const asset = media.data?.find((m) => m.id === p.media_id);
            return (
              <article key={p.id} className="list-item">
                <div style={{ width: "100%" }}>
                  <div className="row" style={{ alignItems: "flex-start" }}>
                    {asset?.thumbnail_url && (
                      <Image
                        unoptimized
                        src={asset.thumbnail_url}
                        alt="Video thumbnail"
                        width={70}
                        height={90}
                        style={{ objectFit: "cover", borderRadius: 5 }}
                      />
                    )}
                    <div style={{ flex: 1 }}>
                      <h3>
                        {p.caption || asset?.filename || "Untitled video"}
                      </h3>
                      <p>
                        Created {dateLabel(p.created_at, p.timezone)} ·{" "}
                        {p.timezone}
                      </p>
                      {p.targets.map((t) => (
                        <div
                          key={t.id}
                          style={{
                            padding: "12px 0",
                            borderTop: "1px solid var(--line)",
                          }}
                        >
                          <div className="row spread">
                            <span>
                              {t.username}{" "}
                              <span className="subtle">
                                · {statusLabel(t.format)}
                              </span>
                            </span>
                            <span className={`badge ${t.status}`}>
                              {statusLabel(t.status)}
                            </span>
                          </div>
                          <p>
                            Scheduled {dateLabel(t.scheduled_at, p.timezone)}
                            {t.published_at &&
                              ` · Published ${dateLabel(t.published_at, p.timezone)}`}
                          </p>
                          {t.error && (
                            <div className="error" style={{ margin: "8px 0" }}>
                              {t.error}
                            </div>
                          )}
                          {t.status === "draft_uploaded" && (
                            <p>
                              Open TikTok and finish this post from your inbox.
                            </p>
                          )}
                          {t.external_url && (
                            <a
                              href={t.external_url}
                              target="_blank"
                              rel="noreferrer"
                              className="subtle"
                            >
                              View publication ↗
                            </a>
                          )}
                        </div>
                      ))}
                      <div className="actions">
                        {p.targets.every((t) =>
                          ["draft", "cancelled"].includes(t.status),
                        ) && (
                          <>
                            <Button asChild size="sm" variant="outline">
                              <Link href={`/create?edit=${p.id}`}>
                                Edit draft
                              </Link>
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={action.isPending}
                              onClick={() => {
                                if (window.confirm("Delete this draft?"))
                                  action.mutate({ id: p.id, remove: true });
                              }}
                            >
                              Delete
                            </Button>
                          </>
                        )}
                        {p.targets.some((t) =>
                          ["scheduled", "queued", "retry"].includes(t.status),
                        ) && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={action.isPending}
                            onClick={() => action.mutate({ id: p.id })}
                          >
                            Cancel publishing
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            );
          })
        ) : (
          <Empty
            title={
              kind === "drafts"
                ? "The next idea starts here."
                : kind === "scheduled"
                  ? "Nothing scheduled yet."
                  : "Your story is just getting started."
            }
            description="Create a post to begin filling your workspace with content."
          >
            <Button asChild variant="outline">
              <Link href="/create">Create post</Link>
            </Button>
          </Empty>
        )}
      </div>
      <p className="subtle" style={{ marginTop: 16 }}>
        Showing the latest 50 posts. Status updates refresh every 30 seconds.
      </p>
    </>
  );
}
