import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.accounts import router as accounts_router
from app.api.media import router as media_router
from app.api.posts import router as posts_router
from app.api.users import router as users_router
from app.core.config import get_settings
from app.core.middleware import SecurityMiddleware


def safe_sentry_event(event, hint):
    return {
        "event_id": event.get("event_id"),
        "level": "error",
        "message": "Uploadio unhandled error",
    }


settings = get_settings()
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=False,
        include_local_variables=False,
        before_send=safe_sentry_event,
    )

app = FastAPI(title="Uploadio API", version="0.1.0")
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Workspace-ID"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(users_router)


app.include_router(media_router)

app.include_router(accounts_router)

app.include_router(posts_router)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})
