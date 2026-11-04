"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Instagram, Link2, Plus } from "lucide-react";
import { Account, api } from "@/lib/api";
import { Empty, ErrorNotice, PageHeading } from "@/components/common";
import { Button } from "@/components/ui/button";
export default function Accounts() {
  const queries = useQueryClient();
  const [notice, setNotice] = useState("");
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api<Account[]>("/social-accounts"),
  });
  const connect = useMutation({
    mutationFn: (platform: string) =>
      api<{ url: string }>(`/social-accounts/${platform}/connect`),
    onSuccess: (data) => window.location.assign(data.url),
  });
  const disconnect = useMutation({
    mutationFn: (id: string) =>
      api(`/social-accounts/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queries.invalidateQueries({ queryKey: ["accounts"] });
      setNotice("Account disconnected and credentials removed.");
    },
  });
  return (
    <>
      <PageHeading
        title="Your corners of the internet."
        subtitle="Connect with official authorization. Your passwords stay with each platform."
      />
      <ErrorNotice
        error={accounts.error || connect.error || disconnect.error}
      />
      {notice && <div className="success">{notice}</div>}
      <div
        className="grid"
        style={{
          gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))",
          marginBottom: 25,
        }}
      >
        <section className="panel">
          <div className="panel-body">
            <div className="account-icon">
              <Link2 size={20} />
            </div>
            <h2 style={{ marginTop: 20 }}>TikTok</h2>
            <p>
              Send videos to your TikTok inbox. Direct Post becomes available
              after app approval.
            </p>
            <Button
              variant="outline"
              disabled={connect.isPending}
              onClick={() => connect.mutate("tiktok")}
            >
              <Plus size={15} />
              Connect TikTok
            </Button>
          </div>
        </section>
        <section className="panel">
          <div className="panel-body">
            <div className="account-icon">
              <Instagram size={20} />
            </div>
            <h2 style={{ marginTop: 20 }}>Instagram</h2>
            <p>
              Reels and eligible Stories require a professional account and Meta
              app approval.
            </p>
            <Button
              variant="outline"
              disabled={connect.isPending}
              onClick={() => connect.mutate("instagram")}
            >
              <Plus size={15} />
              Connect Instagram
            </Button>
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-head">
          <h2>Connected accounts</h2>
        </div>
        {accounts.isPending ? (
          <div className="loading">Loading accounts…</div>
        ) : accounts.data?.length ? (
          accounts.data.map((a) => (
            <div className="list-item" key={a.id}>
              <div>
                <h3>{a.username}</h3>
                <p>
                  {a.platform} · {a.scopes.join(", ")}
                </p>
                <span className={`badge ${a.status}`}>{a.status}</span>
              </div>
              {a.status !== "disconnected" && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={disconnect.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Disconnect ${a.username}? Pending publishing will be cancelled.`,
                      )
                    )
                      disconnect.mutate(a.id);
                  }}
                >
                  Disconnect
                </Button>
              )}
            </div>
          ))
        ) : (
          <Empty
            title="A home for every channel."
            description="Connect a TikTok account to prepare your first publishing destination."
          />
        )}
      </section>
    </>
  );
}
