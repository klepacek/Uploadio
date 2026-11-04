"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Clock3, Send } from "lucide-react";
import { Account, api, json, Media, Post, Profile } from "@/lib/api";
import { PageHeading, ErrorNotice } from "./common";
import { MediaLibrary } from "./media-library";
import { Button } from "./ui/button";
type Destination = {
  account_id: string;
  format: "tiktok_draft" | "tiktok_direct" | "reel" | "story";
  caption: string;
  settings: Record<string, unknown>;
};
type Creator = {
  creator_nickname: string;
  privacy_level_options: string[];
  comment_disabled: boolean;
  duet_disabled: boolean;
  stitch_disabled: boolean;
  max_video_post_duration_sec: number;
};
export function Composer() {
  const router = useRouter();
  const queries = useQueryClient();
  const [mediaId, setMediaId] = useState("");
  const [caption, setCaption] = useState("");
  const [targets, setTargets] = useState<Destination[]>([]);
  const [consent, setConsent] = useState(false);
  const [when, setWhen] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [timezone, setTimezone] = useState("UTC");
  const [creator, setCreator] = useState<Record<string, Creator>>({});
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api<Account[]>("/social-accounts"),
  });
  const media = useQuery({
    queryKey: ["media"],
    queryFn: () => api<Media[]>("/media"),
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Profile>("/users/me"),
  });
  const [loadError, setLoadError] = useState<Error | null>(null);
  useEffect(() => {
    const edit = new URLSearchParams(window.location.search).get("edit");
    if (edit)
      api<Post>(`/posts/${edit}`)
        .then((p) => {
          setEditId(p.id);
          setMediaId(p.media_id);
          setCaption(p.caption);
          setTimezone(p.timezone);
          setTargets(
            p.targets.map((t) => ({
              account_id: t.account_id,
              format: t.format as Destination["format"],
              caption: t.caption,
              settings: t.settings,
            })),
          );
        })
        .catch(setLoadError);
  }, []);
  const asset = media.data?.find((m) => m.id === mediaId);
  const creatorMutation = useMutation({
    mutationFn: (id: string) =>
      api<Creator>(`/social-accounts/${id}/creator-info`),
    onSuccess: (data, id) => setCreator((old) => ({ ...old, [id]: data })),
  });
  function toggle(account: Account) {
    setConsent(false);
    if (targets.some((t) => t.account_id === account.id))
      setTargets(targets.filter((t) => t.account_id !== account.id));
    else {
      setTargets([
        ...targets,
        {
          account_id: account.id,
          format: account.platform === "instagram" ? "reel" : "tiktok_draft",
          caption: "",
          settings: {
            disable_comment: true,
            disable_duet: true,
            disable_stitch: true,
          },
        },
      ]);
      if (
        account.platform === "tiktok" &&
        account.scopes.includes("video.publish")
      )
        creatorMutation.mutate(account.id);
    }
  }
  function update(index: number, data: Partial<Destination>) {
    setTargets((old) =>
      old.map((t, i) => (i === index ? { ...t, ...data } : t)),
    );
    setConsent(false);
  }
  const save = useMutation({
    mutationFn: async (action: "draft" | "publish" | "schedule") => {
      if (!mediaId || !targets.length)
        throw new Error("Select a validated video and at least one account.");
      if (caption.length > 2200 || targets.some((t) => t.caption.length > 2200))
        throw new Error("Captions must be at most 2,200 characters.");
      if (action !== "draft" && !consent)
        throw new Error("Confirm consent before publishing.");
      if (
        action !== "draft" &&
        targets.some(
          (t) => t.format === "tiktok_direct" && !creator[t.account_id],
        )
      )
        throw new Error(
          "Refresh creator information for every selected account.",
        );
      if (action === "schedule" && (!when || new Date(when) <= new Date()))
        throw new Error("Choose a future date and time.");
      if (
        targets.some(
          (t) => t.format === "tiktok_direct" && !t.settings.privacy_level,
        )
      )
        throw new Error("Choose a privacy level for every Direct Post.");
      for (const target of targets) {
        const info = creator[target.account_id];
        if (
          info &&
          asset &&
          asset.metadata.duration > info.max_video_post_duration_sec
        )
          throw new Error(
            `This video exceeds ${info.creator_nickname}’s duration limit.`,
          );
      }
      const zone = editId ? timezone : profile.data?.timezone || "UTC";
      const post = await api<Post>(
        editId ? `/posts/${editId}` : "/posts",
        json(editId ? "PATCH" : "POST", {
          media_id: mediaId,
          caption,
          timezone: zone,
          targets,
        }),
      );
      setEditId(post.id);
      if (action !== "draft")
        await api(
          `/posts/${post.id}/${action}`,
          json("POST", {
            consent,
            ...(action === "schedule"
              ? { scheduled_at: new Date(when).toISOString() }
              : {}),
          }),
        );
      return action;
    },
    onSuccess: (action) => {
      queries.invalidateQueries({ queryKey: ["posts"] });
      queries.invalidateQueries({ queryKey: ["dashboard"] });
      router.push(action === "draft" ? "/drafts" : "/scheduled");
    },
  });
  return (
    <>
      <PageHeading
        title={editId ? "A little more you." : "Something worth sharing."}
        subtitle="One video. Thoughtful details for every destination."
      />
      <ErrorNotice
        error={
          loadError ||
          save.error ||
          accounts.error ||
          media.error ||
          creatorMutation.error
        }
      />
      <div className="grid form-grid">
        <div>
          <section className="panel" style={{ marginBottom: 20 }}>
            <div className="panel-head">
              <h2>01 · Your video</h2>
              {mediaId && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMediaId("")}
                >
                  Change video
                </Button>
              )}
            </div>
            <div className="panel-body">
              {asset ? (
                <div className="row">
                  <video
                    src={asset.url || undefined}
                    controls
                    className="video-preview"
                    style={{ maxHeight: 220 }}
                  />
                  <div>
                    <h3>{asset.filename}</h3>
                    <p>
                      {asset.metadata.width} × {asset.metadata.height}
                      <br />
                      {Math.round(asset.metadata.duration)} seconds
                    </p>
                  </div>
                </div>
              ) : (
                <MediaLibrary onSelect={setMediaId} />
              )}
            </div>
          </section>
          <section className="panel" style={{ marginBottom: 20 }}>
            <div className="panel-head">
              <h2>02 · Words to go with it</h2>
              <span className="subtle">{caption.length}/2200</span>
            </div>
            <div className="panel-body">
              <label htmlFor="caption">Shared caption & hashtags</label>
              <textarea
                id="caption"
                value={caption}
                maxLength={2200}
                placeholder="Tell the story behind your video…"
                onChange={(e) => {
                  setCaption(e.target.value);
                  setConsent(false);
                }}
              />
              <p className="subtle" style={{ marginBottom: 0 }}>
                Use #hashtags in your caption. Add a custom caption below for
                each destination.
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>03 · Where it’s going</h2>
              <Link href="/accounts" className="subtle">
                Manage accounts ↗
              </Link>
            </div>
            <div className="panel-body">
              {accounts.data?.filter((a) => a.status === "connected").length ? (
                accounts.data
                  .filter((a) => a.status === "connected")
                  .map((a) => {
                    const index = targets.findIndex(
                      (t) => t.account_id === a.id,
                    );
                    const target = targets[index];
                    const info = creator[a.id];
                    return (
                      <div className="destination" key={a.id}>
                        <label className="row">
                          <input
                            type="checkbox"
                            checked={!!target}
                            onChange={() => toggle(a)}
                          />
                          <strong>{a.username}</strong>
                          <span className="badge">{a.platform}</span>
                        </label>
                        {target && (
                          <div className="destination-settings">
                            <div className="field">
                              <label htmlFor={`format-${a.id}`}>
                                Publishing workflow
                              </label>
                              <select
                                id={`format-${a.id}`}
                                value={target.format}
                                onChange={(e) =>
                                  update(index, {
                                    format: e.target
                                      .value as Destination["format"],
                                  })
                                }
                              >
                                {a.platform === "instagram" ? (
                                  <>
                                    <option value="reel">Instagram Reel</option>
                                    <option value="story">
                                      Instagram Story
                                    </option>
                                  </>
                                ) : (
                                  <option value="tiktok_draft">
                                    Upload to TikTok inbox
                                  </option>
                                )}
                                {a.scopes.includes("video.publish") && (
                                  <option value="tiktok_direct">
                                    Direct Post
                                  </option>
                                )}
                              </select>
                            </div>
                            {a.platform === "tiktok" &&
                              a.scopes.includes("video.publish") &&
                              (info ? (
                                <p className="subtle">
                                  Posting as {info.creator_nickname} · maximum{" "}
                                  {info.max_video_post_duration_sec}s
                                </p>
                              ) : (
                                <p className="subtle">
                                  Creator information is required before
                                  publishing.
                                </p>
                              ))}
                            {a.platform === "tiktok" &&
                              a.scopes.includes("video.publish") && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  disabled={creatorMutation.isPending}
                                  onClick={() => creatorMutation.mutate(a.id)}
                                >
                                  Refresh creator information
                                </Button>
                              )}
                            {target.format === "tiktok_direct" && (
                              <>
                                <div className="field">
                                  <label htmlFor={`privacy-${a.id}`}>
                                    Who can watch?
                                  </label>
                                  <select
                                    id={`privacy-${a.id}`}
                                    value={String(
                                      target.settings.privacy_level || "",
                                    )}
                                    onChange={(e) =>
                                      update(index, {
                                        settings: {
                                          ...target.settings,
                                          privacy_level: e.target.value,
                                        },
                                      })
                                    }
                                  >
                                    <option value="">
                                      Choose a privacy level
                                    </option>
                                    {info?.privacy_level_options.map((p) => (
                                      <option key={p} value={p}>
                                        {p.replaceAll("_", " ").toLowerCase()}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                                {(["comment", "duet", "stitch"] as const).map(
                                  (key) => (
                                    <label className="row" key={key}>
                                      <input
                                        type="checkbox"
                                        checked={
                                          !target.settings[`disable_${key}`]
                                        }
                                        disabled={
                                          !info || info[`${key}_disabled`]
                                        }
                                        onChange={(e) =>
                                          update(index, {
                                            settings: {
                                              ...target.settings,
                                              [`disable_${key}`]:
                                                !e.target.checked,
                                            },
                                          })
                                        }
                                      />
                                      Allow {key}
                                    </label>
                                  ),
                                )}
                                {[
                                  "brand_content_toggle",
                                  "brand_organic_toggle",
                                ].map((key, i) => (
                                  <label className="row" key={key}>
                                    <input
                                      type="checkbox"
                                      checked={!!target.settings[key]}
                                      onChange={(e) =>
                                        update(index, {
                                          settings: {
                                            ...target.settings,
                                            [key]: e.target.checked,
                                          },
                                        })
                                      }
                                    />
                                    {i === 0
                                      ? "Branded content / paid partnership"
                                      : "Promoting my own business"}
                                  </label>
                                ))}
                              </>
                            )}
                            <div className="field" style={{ marginTop: 15 }}>
                              <label htmlFor={`caption-${a.id}`}>
                                Custom caption (optional)
                              </label>
                              <textarea
                                id={`caption-${a.id}`}
                                maxLength={2200}
                                value={target.caption}
                                placeholder="Use the shared caption"
                                onChange={(e) =>
                                  update(index, { caption: e.target.value })
                                }
                              />
                            </div>
                            <div className="note" style={{ marginBottom: 0 }}>
                              {target.format === "tiktok_draft"
                                ? "This sends a video to your TikTok inbox. You’ll finish editing and publish it in TikTok. Captions must be added in TikTok’s editing flow."
                                : target.format === "story"
                                  ? "Stories do not support captions. Use an eligible business account and a video between 3 and 60 seconds."
                                  : target.format === "reel"
                                    ? "Reels use your shared or custom caption. Media is processed by Instagram before publication."
                                    : "Direct Post requires app approval. You stay in control of privacy and interactions."}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
              ) : (
                <p>
                  Connect an account in{" "}
                  <Link href="/accounts" style={{ color: "var(--accent)" }}>
                    Connected accounts
                  </Link>{" "}
                  to choose a destination.
                </p>
              )}
              <p className="subtle" style={{ marginTop: 20 }}>
                Instagram requires a professional account and approved
                publishing access. Stories require an eligible business account.
              </p>
            </div>
          </section>
          <div className="panel" style={{ marginTop: 20 }}>
            <div className="panel-body">
              <label htmlFor="schedule">
                Schedule time (your device’s local timezone)
              </label>
              <input
                id="schedule"
                type="datetime-local"
                value={when}
                onChange={(e) => setWhen(e.target.value)}
              />
              <p className="subtle">
                Times are stored in UTC. Your profile timezone is used for
                display.
              </p>
              <label className="consent">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                I consent to Uploadio sending this video to the selected
                accounts using the settings above. For Direct Post, I agree to
                TikTok’s Music Usage Confirmation.
              </label>
              <p className="subtle">
                <a
                  href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en"
                  target="_blank"
                  rel="noreferrer"
                >
                  Music Usage Confirmation ↗
                </a>
              </p>
              <div className="actions">
                <Button
                  variant="outline"
                  disabled={save.isPending}
                  onClick={() => save.mutate("draft")}
                >
                  Save draft
                </Button>
                <Button
                  variant="outline"
                  disabled={save.isPending}
                  onClick={() => save.mutate("schedule")}
                >
                  <Clock3 size={15} />
                  Schedule
                </Button>
                <Button
                  disabled={save.isPending}
                  onClick={() => save.mutate("publish")}
                >
                  <Send size={15} />
                  {save.isPending
                    ? "Saving…"
                    : targets.every((t) => t.format === "tiktok_draft")
                      ? "Send to TikTok inbox"
                      : "Publish now"}
                </Button>
              </div>
            </div>
          </div>
        </div>
        <aside className="preview-column">
          <div className="section-label" style={{ marginTop: 0 }}>
            A quick preview
          </div>
          <div className="preview-phone">
            {asset?.url ? (
              <video controls src={asset.url} />
            ) : (
              <div
                style={{
                  minHeight: 330,
                  display: "grid",
                  placeItems: "center",
                  color: "var(--muted)",
                }}
              >
                Your video goes here
              </div>
            )}
            <div className="preview-caption">
              <strong>
                {targets.length
                  ? accounts.data?.find((a) => a.id === targets[0].account_id)
                      ?.username
                  : "Your account"}
              </strong>
              <p style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>
                {targets[0]?.caption ||
                  caption ||
                  "Your story, in a few words."}
              </p>
            </div>
          </div>
          <p className="subtle" style={{ padding: "15px 5px" }}>
            Preview is approximate. Each platform controls its final appearance.
          </p>
          <Link className="row subtle" href="/drafts">
            <ArrowLeft size={14} />
            Back to drafts
          </Link>
        </aside>
      </div>
    </>
  );
}
