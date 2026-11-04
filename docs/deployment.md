# Setup and deployment

## Local configuration

Use Python 3.12+, Node.js 22+, PostgreSQL 16+, Redis 7+, FFmpeg and ffprobe. The tested local Python runtime was 3.14; CI targets 3.12. Docker Compose is the recommended full-stack setup.

```sh
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Set real values before starting authenticated workflows. Generate a token key:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Keep that key stable and backed up in a secret manager. Replacing it without a token migration makes existing OAuth credentials unreadable. Do not commit generated keys or environment files.

Docker reads the root `.env`. Native backend development reads `backend/.env`, so copy the root configuration there and adjust service URLs for localhost. The frontend receives only the public variables from its own example.

## Supabase Auth

Create a Supabase project, enable email/password authentication and email confirmation, set your site URL, and allow these redirect URLs for each environment:

```text
http://localhost:3000/auth/callback
http://localhost:3000/auth/callback?next=reset
https://app.example.com/auth/callback
https://app.example.com/auth/callback?next=reset
```

Configure production SMTP, password policy, and abuse protection in Supabase. Never expose a service-role key. `SUPABASE_PUBLISHABLE_KEY` and its frontend counterpart are publishable keys, not service-role secrets. The API uses the user endpoint to validate live access tokens, including projects using asymmetric signing keys.

The application can use a separate PostgreSQL instance or the Supabase database. Run Alembic against the intended database using a direct/session-compatible connection. Keep application tables inaccessible through the Supabase Data API. Supabase supplies authentication, not automatic application-table access.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL URL; use TLS in production |
| `REDIS_URL` | Private Redis broker and limiter URL; use authentication/TLS where needed |
| `FRONTEND_URL` | Exact allowed CORS origin and OAuth return destination |
| `API_URL` | Public API origin used to construct OAuth callbacks |
| `SUPABASE_URL` | Supabase project origin |
| `SUPABASE_PUBLISHABLE_KEY` | Publishable key for server-side token validation |
| `TOKEN_ENCRYPTION_KEY` | Fernet key used for encrypted social tokens and PKCE verifier |
| `R2_ENDPOINT_URL` | Account-specific S3-compatible R2 endpoint |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Bucket-scoped R2 credentials |
| `R2_BUCKET` | Private bucket name |
| `MAX_UPLOAD_BYTES` | Source-file maximum; defaults to 500,000,000 |
| `WORKSPACE_QUOTA_BYTES` | Source-file quota; defaults to 5,000,000,000 |
| `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | Instagram product credentials from Meta |
| `INSTAGRAM_API_VERSION` | Pinned Graph API version; defaults to `v24.0` |
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` | TikTok app credentials |
| `TIKTOK_DIRECT_POST_ENABLED` | Defaults to false; enable only after appropriate approval |
| `SENTRY_DSN` | Optional API error reporting; event content is stripped to avoid tokens/PII |
| `RATE_LIMIT_ENABLED` | Defaults to true; leave enabled outside tests |
| `NEXT_PUBLIC_API_URL` | Browser-accessible API URL including `/api/v1` |
| `NEXT_PUBLIC_SUPABASE_URL` | Public Supabase project origin |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Public Supabase publishable key |

Next.js embeds public variables at build time. Rebuild the frontend when these change. Do not put secrets in variables beginning `NEXT_PUBLIC_`.

## R2

Create a private bucket and credentials restricted to that bucket. Allow browser uploads from your exact frontend origins with bucket CORS:

```json
[{"AllowedOrigins":["http://localhost:3000","https://app.example.com"],"AllowedMethods":["PUT","GET","HEAD"],"AllowedHeaders":["Content-Type"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":3600}]
```

Add a one-day expiration rule for objects under `staging/`. Do not expose a public bucket endpoint. Meta fetches time-limited signed download URLs. TikTok receives streamed chunks from the backend. Failed pending uploads can be removed through the media library.

## Run with Docker

```sh
docker compose up --build
```

Compose starts PostgreSQL, Redis, migrations, API, worker, scheduler and frontend. API and worker wait for successful migrations. Open `http://localhost:3000`; API docs are at `http://localhost:8000/docs`.

Compose binds ports to localhost and uses development database credentials. Replace those credentials and network settings for a commercial deployment. Do not expose PostgreSQL or Redis publicly.

## Run services natively

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
pip install --no-deps -e .
alembic upgrade head
uvicorn app.main:app --reload --no-access-log
```

In separate backend terminals with the environment activated:

```sh
celery -A app.workers.tasks.celery_app worker --loglevel=info
celery -A app.workers.tasks.celery_app beat --loglevel=info --schedule=/tmp/uploadio-celerybeat
```

```sh
cd frontend
npm ci
npm run dev -- --webpack
```

## Production services

Deploy the frontend, API, worker and one Beat scheduler separately. Use HTTPS on frontend/API, a private database and Redis, persistent database backups, R2 lifecycle rules, and secret-manager injection. Run `alembic upgrade head` as a single release job before starting the new services. Test migrations against a restored production snapshot before release; do not run destructive downgrades against live data as a rollback strategy.

Configure the reverse proxy to enforce request-body and timeout limits, and limit trusted forwarded proxies. The API limits requests by the connection IP, so preserve actual client addresses only through a trusted proxy; do not allow arbitrary forwarded-IP spoofing. Configure no access logging for OAuth query strings: callbacks contain authorization codes. Keep HTTPX debug logging disabled.

FFmpeg runs with protocol restrictions and execution timeouts, but process isolation is also required for hostile media. Use container memory/CPU limits, a read-only root filesystem where practical, bounded temporary storage, and current FFmpeg security updates. Media inspection currently occupies an API request; move it to a separate queue before high upload volume or configure sufficient proxy timeouts.

Sentry currently reports sanitized API errors. Worker failures are persisted in publishing attempts and target errors; configure additional sanitized worker monitoring before commercial release.

## Release gate

Do not open public commercial access until CI is green, the [live integration checklist](integrations.md#live-verification-still-required) passes, and live browser verification covers registration, recovery, upload, composer, scheduling, and history against your configured environment. The included Playwright suite exercises public flows and an empty workspace using test API responses on desktop and mobile; it does not establish live provider behavior. Verify platform approval, application privacy/data deletion pages, operational alerting, backups/restores, retention, and support procedures.
