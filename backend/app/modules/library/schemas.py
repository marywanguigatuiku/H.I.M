import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    size: int
    created_at: dt.datetime
    last_page: int
    last_paragraph: int
    shared: bool = False  # true when somebody else owns it and shared it with you


class ProgressIn(BaseModel):
    page: int
    paragraph: int


class NoteIn(BaseModel):
    document_id: str
    page: int
    paragraph: Optional[int] = None
    body: str = ""
    updated_at: dt.datetime
    deleted: bool = False


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    page: int
    paragraph: Optional[int] = None
    body: str
    updated_at: dt.datetime
    deleted: bool
