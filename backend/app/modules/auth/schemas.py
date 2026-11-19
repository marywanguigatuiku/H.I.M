import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Credentials(BaseModel):
    email: str
    password: str
    invite_code: str = ""


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    role: str
    apps: list[str]
    is_active: bool = True


class MeOut(BaseModel):
    user: UserOut
    home: str  # where the app should send this person: "/", "/transcribe/" or "/admin/"


class AuthOut(MeOut):
    token: str


class AdminUserOut(UserOut):
    created_at: Optional[dt.datetime] = None
    last_login_at: Optional[dt.datetime] = None
