import uuid
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import User, Workspace, WorkspaceMember

Db = Annotated[AsyncSession, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


async def current_user(
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(401, "Sign in to continue")
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(503, "Authentication is not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {credentials.credentials}",
                    "apikey": settings.supabase_publishable_key,
                },
            )
        if response.status_code in (401, 403):
            raise HTTPException(401, "Session expired; sign in again")
        response.raise_for_status()
        data = response.json()
        user_id = uuid.UUID(data["id"])
        if not data.get("email_confirmed_at"):
            raise HTTPException(403, "Verify your email to continue")
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Authentication service unavailable") from exc
    user = await db.get(User, user_id)
    if user is None:
        # The lock serializes first-login provisioning across API processes.
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy import text

            await db.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": user_id.int % (2**63 - 1)},
            )
            user = await db.get(User, user_id)
        if user is None:
            user = User(id=user_id, email=data.get("email", ""))
            db.add(user)
            await db.flush()
            workspace = Workspace(owner_id=user.id, name="Personal workspace")
            db.add(workspace)
            await db.flush()
            db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
            await db.flush()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def current_workspace(
    db: Db,
    user: CurrentUser,
    workspace_id: Annotated[uuid.UUID | None, Header(alias="X-Workspace-ID")] = None,
) -> Workspace:
    query = select(Workspace).join(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    if workspace_id:
        query = query.where(Workspace.id == workspace_id)
    else:
        query = query.where(Workspace.owner_id == user.id)
    workspace = await db.scalar(query)
    if workspace is None:
        raise HTTPException(404, "Workspace not found")
    return workspace


CurrentWorkspace = Annotated[Workspace, Depends(current_workspace)]
