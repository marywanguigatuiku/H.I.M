import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.schemas import AdminUserOut


class AdminUserRow(AdminUserOut):
    documents: int = 0


class UserPatch(BaseModel):
    role: Optional[str] = None
    apps: Optional[list[str]] = None
    is_active: Optional[bool] = None


class InviteIn(BaseModel):
    email: str
    apps: list[str] = Field(default_factory=lambda: ["library"])
    role: str = "user"


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    apps: list[str]
    role: str
    created_at: dt.datetime


class Overview(BaseModel):
    users: int
    active_users: int
    admins: int
    pending_invites: int
    documents: int
    notes: int
    transcriptions: int = 0
    minutes_transcribed: int = 0


class ShareLabel(BaseModel):
    kind: str  # "all" | "group" | "user"
    label: str


class BookRow(BaseModel):
    id: str
    title: str
    size: int
    created_at: dt.datetime
    owner_email: str
    shared_with: list[ShareLabel]
    everyone: bool = False
    group_ids: list[str] = Field(default_factory=list)
    user_ids: list[str] = Field(default_factory=list)
    opens: int = 0
    readers: int = 0


class SharesIn(BaseModel):
    everyone: bool = False
    groups: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)


class PersonRef(BaseModel):
    id: str
    email: str


class GroupRow(BaseModel):
    id: str
    name: str
    members: list[PersonRef]


class GroupCreate(BaseModel):
    name: str


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    members: Optional[list[str]] = None


class DailyOpens(BaseModel):
    date: str
    opens: int


class UsageBook(BaseModel):
    id: str
    title: str
    opens: int
    readers: int


class UsagePerson(BaseModel):
    user_id: str
    email: str
    events: int
    last_active: Optional[dt.datetime] = None
    recordings: int = 0
    minutes: int = 0


class UsageReport(BaseModel):
    days: int
    opens: int
    active_people: int
    recordings: int
    minutes: int
    daily: list[DailyOpens]
    top_books: list[UsageBook]
    people: list[UsagePerson]
