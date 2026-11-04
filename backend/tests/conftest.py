import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.auth import current_user
from app.db.session import get_db
from app.main import app
from app.models.entities import Base, User, Workspace, WorkspaceMember


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def user(db):
    user = User(id=uuid.uuid4(), email="owner@example.com")
    db.add(user)
    await db.flush()
    workspace = Workspace(owner_id=user.id, name="Personal")
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    await db.commit()
    return user


@pytest.fixture
async def client(db, user):
    async def database():
        yield db
        await db.commit()

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[current_user] = lambda: user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
