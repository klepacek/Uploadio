"use client";
import Image from "next/image";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { api, json, Media } from "@/lib/api";
import { Empty, ErrorNotice, PageHeading } from "./common";
import { Button } from "./ui/button";
export function MediaLibrary({
  onSelect,
}: {
  onSelect?: (id: string) => void;
}) {
  const queries = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState("");
  const media = useQuery({
    queryKey: ["media"],
    queryFn: () => api<Media[]>("/media"),
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > 500_000_000 || !/\.(mp4|mov)$/i.test(file.name))
        throw new Error("Choose an MP4 or MOV video under 500 MB.");
      setProgress("Preparing a private upload…");
      const contentType = /\.mov$/i.test(file.name)
        ? "video/quicktime"
        : "video/mp4";
      const result = await api<{ media_id: string; upload_url: string }>(
        "/media/upload-url",
        json("POST", {
          filename: file.name.toLowerCase(),
          content_type: contentType,
          size_bytes: file.size,
        }),
      );
      setProgress("Uploading video…");
      const response = await fetch(result.upload_url, {
        method: "PUT",
        headers: { "Content-Type": contentType },
        body: file,
      });
      if (!response.ok)
        throw new Error(
          "Upload failed. Check your connection and R2 CORS configuration.",
        );
      setProgress("Checking your video and creating a thumbnail…");
      await api("/media/complete", json("POST", { media_id: result.media_id }));
      return result.media_id;
    },
    onSuccess: (id) => {
      queries.invalidateQueries({ queryKey: ["media"] });
      onSelect?.(id);
      setProgress("");
    },
    onError: () => setProgress(""),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/media/${id}`, { method: "DELETE" }),
    onSuccess: () => queries.invalidateQueries({ queryKey: ["media"] }),
  });
  const inspect = useMutation({
    mutationFn: (id: string) =>
      api("/media/complete", json("POST", { media_id: id })),
    onSuccess: () => queries.invalidateQueries({ queryKey: ["media"] }),
  });
  return (
    <>
      {!onSelect && (
        <PageHeading
          title="Good content starts here."
          subtitle="Your private video library. Up to 500 MB per upload."
        />
      )}
      <ErrorNotice
        error={upload.error || remove.error || media.error || inspect.error}
      />
      <div className="upload-area" style={{ marginBottom: 25 }}>
        <Upload
          size={25}
          color="var(--accent)"
          style={{ margin: "0 auto 10px" }}
        />
        <h3>Bring your next video.</h3>
        <p className="subtle">MP4 or MOV · H.264 or H.265 · up to 10 minutes</p>
        <input
          ref={input}
          type="file"
          aria-label="Upload video"
          accept="video/mp4,video/quicktime,.mp4,.mov"
          disabled={upload.isPending}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) upload.mutate(file);
            event.target.value = "";
          }}
        />
        {progress && (
          <p role="status" style={{ color: "var(--accent)", marginTop: 15 }}>
            {progress}
          </p>
        )}
      </div>
      {media.isPending ? (
        <div className="loading">Loading library…</div>
      ) : media.data?.length ? (
        <div className="grid media-grid">
          {media.data.map((m) => (
            <article key={m.id} className="panel media-card">
              {m.thumbnail_url && (
                <Image
                  unoptimized
                  width={480}
                  height={300}
                  src={m.thumbnail_url}
                  alt={`Thumbnail of ${m.filename}`}
                />
              )}
              <div className="panel-body">
                <h3>{m.filename}</h3>
                <p>
                  {(m.size_bytes / 1_000_000).toFixed(1)} MB ·{" "}
                  {m.status === "ready"
                    ? `${Math.round(m.metadata.duration)}s · ${m.metadata.width}×${m.metadata.height}`
                    : "Awaiting validation"}
                </p>
                <div className="actions">
                  {onSelect && m.status === "ready" && (
                    <Button size="sm" onClick={() => onSelect(m.id)}>
                      Use video
                    </Button>
                  )}
                  {m.url && !onSelect && (
                    <Button asChild variant="outline" size="sm">
                      <a href={m.url} target="_blank" rel="noreferrer">
                        Preview
                      </a>
                    </Button>
                  )}
                  {m.status === "pending" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={inspect.isPending}
                      onClick={() => inspect.mutate(m.id)}
                    >
                      Check upload
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm("Permanently delete this video?"))
                        remove.mutate(m.id);
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="A clean slate."
          description="Upload a video to start building your content library."
        />
      )}
    </>
  );
}
