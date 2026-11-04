import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.schemas.users import ProfileUpdate


class TargetInput(BaseModel):
    account_id: uuid.UUID
    format: Literal["reel", "story", "tiktok_draft", "tiktok_direct"]
    caption: str = Field(default="", max_length=2200)
    settings: dict = Field(default_factory=dict)


class PostInput(BaseModel):
    media_id: uuid.UUID
    caption: str = Field(default="", max_length=2200)
    timezone: str = "UTC"
    targets: list[TargetInput] = Field(min_length=1, max_length=20)

    def validate_timezone(self):
        ProfileUpdate(display_name="", timezone=self.timezone)


class DispatchInput(BaseModel):
    consent: bool = False


class ScheduleInput(DispatchInput):
    scheduled_at: AwareDatetime


class TargetOutput(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    username: str
    platform: str
    format: str
    caption: str
    settings: dict
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    external_url: str | None
    error: str | None


class PostOutput(BaseModel):
    id: uuid.UUID
    media_id: uuid.UUID
    caption: str
    timezone: str
    created_at: datetime
    targets: list[TargetOutput]
