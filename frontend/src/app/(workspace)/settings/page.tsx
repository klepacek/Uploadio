"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, json, Profile } from "@/lib/api";
import { ErrorNotice, PageHeading } from "@/components/common";
import { Button } from "@/components/ui/button";
export default function Settings() {
  const queries = useQueryClient();
  const [saved, setSaved] = useState(false);
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Profile>("/users/me"),
  });
  const update = useMutation({
    mutationFn: (data: { display_name: string; timezone: string }) =>
      api("/users/me", json("PATCH", data)),
    onSuccess: () => {
      queries.invalidateQueries({ queryKey: ["profile"] });
      setSaved(true);
    },
  });
  return (
    <>
      <PageHeading
        title="Make yourself at home."
        subtitle="A few details to keep your workspace feeling like yours."
      />
      <ErrorNotice error={profile.error || update.error} />
      {saved && (
        <div className="success" role="status">
          Your profile has been updated.
        </div>
      )}
      <section className="panel" style={{ maxWidth: 650 }}>
        <div className="panel-head">
          <h2>Profile & preferences</h2>
        </div>
        <div className="panel-body">
          {profile.data ? (
            <form
              key={profile.data.display_name + profile.data.timezone}
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                setSaved(false);
                update.mutate({
                  display_name: String(form.get("display_name")),
                  timezone: String(form.get("timezone")),
                });
              }}
            >
              <div className="field">
                <label htmlFor="email">Email address</label>
                <input id="email" value={profile.data.email} disabled />
              </div>
              <div className="field">
                <label htmlFor="name">Display name</label>
                <input
                  id="name"
                  name="display_name"
                  maxLength={100}
                  defaultValue={profile.data.display_name}
                />
              </div>
              <div className="field">
                <label htmlFor="timezone">Display timezone</label>
                <input
                  id="timezone"
                  name="timezone"
                  required
                  defaultValue={profile.data.timezone}
                  list="timezones"
                />
                <datalist id="timezones">
                  {Intl.supportedValuesOf("timeZone").map((zone) => (
                    <option key={zone} value={zone} />
                  ))}
                </datalist>
                <p className="subtle">
                  Use an IANA timezone, such as Europe/Prague. Scheduling uses
                  your device’s local time.
                </p>
              </div>
              <Button disabled={update.isPending}>
                {update.isPending ? "Saving…" : "Save changes"}
              </Button>
            </form>
          ) : (
            <div className="loading">Loading profile…</div>
          )}
        </div>
      </section>
    </>
  );
}
