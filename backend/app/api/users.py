from fastapi import APIRouter
from sqlalchemy import select

from app.core.auth import CurrentUser, CurrentWorkspace, Db
from app.models.entities import Workspace, WorkspaceMember
from app.schemas.users import ProfileUpdate

router = APIRouter(prefix="/api/v1")


@router.get("/users/me")
async def me(user: CurrentUser, workspace: CurrentWorkspace):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "timezone": user.timezone,
        "workspace_id": workspace.id,
    }


@router.patch("/users/me")
async def update_me(data: ProfileUpdate, user: CurrentUser, db: Db):
    user.display_name = data.display_name
    user.timezone = data.timezone
    await db.flush()
    return {"display_name": user.display_name, "timezone": user.timezone}


@router.get("/workspaces")
async def workspaces(user: CurrentUser, db: Db):
    rows = await db.scalars(
        select(Workspace).join(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    )
    return [{"id": row.id, "name": row.name} for row in rows]
