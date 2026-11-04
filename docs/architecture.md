# Architecture

Next.js handles presentation and browser sessions. FastAPI owns authorization, media inspection, social integration credentials, post state, and scheduling. Celery workers perform publishing; Celery Beat scans persistent database records every 15 seconds. PostgreSQL is the source of truth. Redis is a broker and a shared request limiter, not the schedule database.

## Authorization

FastAPI validates the supplied bearer token with Supabase's `/auth/v1/user` endpoint on every authenticated request. It uses the verified user ID, requires email confirmation, and provisions a personal workspace on first API access. PostgreSQL advisory locking serializes first-login provisioning. It never accepts a frontend user ID as an authority.

All resource queries are scoped to a workspace selected through database membership. A user can supply `X-Workspace-ID`, but access still requires membership. Owners and members have the same publishing abilities in this MVP. Collaboration invitations and membership management are not exposed yet.

Application tables have RLS enabled with no Data API policies, and access is revoked from `anon`, `authenticated`, and PUBLIC. Only the backend connects directly. Use a dedicated application role that owns these tables, since table owners bypass RLS; do not put its credentials in the frontend. Do not grant browser roles table privileges.

The API uses bearer authorization rather than authentication cookies, so cross-site forms cannot silently authenticate API mutations. OAuth callbacks use random, expiring, one-use database state. PKCE is included for TikTok; the reviewed Instagram web flow does not document PKCE.

## Media

Uploads reserve quota under a workspace row lock, then receive a short-lived signed R2 PUT URL with an exact content type and length. Completion checks object size and ETag, downloads a bounded file, runs ffprobe and FFmpeg with file-only protocols and timeouts, creates a thumbnail, and conditionally copies the inspected object into a separate `media/` key. Upload credentials only allow writing to `staging/` keys. A later reuse of the upload URL cannot overwrite publishable media.

Source and thumbnail objects are private. Signed GET URLs expire after one hour. Configure a one-day lifecycle rule for `staging/` objects to clean up failed uploads and any reuse of expired staging reservations. Pending reservations count against quota and can be deleted from the library. Quotas account for source sizes; thumbnails, temporary staging copies and object-store overhead are additional.

The application rejects unsupported input rather than transcoding every upload. Platform validation checks size, duration, dimensions, frame rate, and relevant audio/video metadata. Final container details such as edit lists, closed GOP structure, and Meta processing acceptance still require the platform's validation.

## Publishing state

Each post contains independent targets. A target carries its own account, format, caption, settings, consent time, schedule, provider IDs, and status. History can therefore represent partial success without a misleading shared success flag.

Typical transitions:

```text
draft -> scheduled -> queued -> processing -> published
                                        -> draft_uploaded (TikTok inbox)
                                        -> failed
                                        -> retry -> queued
                                        -> uncertain
scheduled / queued / retry -> cancelled
```

The scheduler claims due rows with `FOR UPDATE SKIP LOCKED`. Workers claim a queued target with an atomic conditional update. Task IDs correspond to target IDs, but database state provides duplicate protection. A unique attempt number tracks each execution.

Queued leases expire after two minutes and are redispatched. Processing leases without a provider ID become `uncertain` after interruption. Processing jobs with a provider ID are reconciled using that ID. Retryable explicit rejections use bounded exponential backoff; ambiguous network outcomes never create a fresh publishing submission automatically.

Instagram records `publish_submitted_at` before submitting a ready container. Reconciliation can confirm a lost successful response. A still-unconfirmed submission becomes uncertain instead of being sent twice.

## Operational limits

The system favors avoiding duplicate publication over automatic recovery from every failure. Uncertain jobs require operator review of the provider account. There is no operator resolution UI yet. TikTok inbox status polling stops after delivery; Uploadio does not subsequently monitor whether the creator publishes that inbox item.

Post updates and cancellation lock targets. Cancellation succeeds only before processing starts. Account disconnection revokes a connected token, clears encrypted credentials, and cancels queued/scheduled jobs. Disconnection is refused while a target is processing or uncertain. Revocation failures are shown instead of being reported as a successful disconnect.

Database schemas and infrastructure are ready for multiple API and worker instances. Concurrency behavior is covered by a PostgreSQL-specific CI test; SQLite tests alone do not establish PostgreSQL lock behavior.
