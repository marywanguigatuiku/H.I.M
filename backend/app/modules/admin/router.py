from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin import service
from app.modules.admin.schemas import (AdminUserRow, BookRow, GroupCreate, GroupRow, GroupUpdate, InviteIn, InviteOut, Overview,
                                       SharesIn, UsageReport, UserPatch)
from app.modules.auth.deps import require_admin
from app.modules.auth.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview", response_model=Overview)
def overview(db: Session = Depends(get_db)):
    return service.overview(db)


@router.get("/users", response_model=list[AdminUserRow])
def list_users(db: Session = Depends(get_db)):
    return service.list_users(db)


@router.patch("/users/{user_id}", response_model=AdminUserRow)
def update_user(user_id: str, patch: UserPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_user(db, admin, user_id, patch)


@router.get("/invites", response_model=list[InviteOut])
def list_invites(db: Session = Depends(get_db)):
    return service.list_invites(db)


@router.post("/invites", response_model=InviteOut)
def create_invite(data: InviteIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.create_invite(db, admin, data)


@router.delete("/invites/{invite_id}", status_code=204)
def delete_invite(invite_id: str, db: Session = Depends(get_db)):
    service.delete_invite(db, invite_id)


@router.get("/books", response_model=list[BookRow])
def list_books(db: Session = Depends(get_db)):
    return service.list_books(db)


@router.post("/books", response_model=BookRow)
async def create_book(file: UploadFile = File(...), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return await service.create_book(db, admin, file)


@router.put("/books/{doc_id}/shares", response_model=BookRow)
def share_book(doc_id: str, data: SharesIn, db: Session = Depends(get_db)):
    return service.share_book(db, doc_id, data.everyone, data.groups, data.users)


@router.delete("/books/{doc_id}", status_code=204)
def delete_book(doc_id: str, db: Session = Depends(get_db)):
    service.delete_book(db, doc_id)


@router.get("/groups", response_model=list[GroupRow])
def list_groups(db: Session = Depends(get_db)):
    return service.list_groups(db)


@router.post("/groups", response_model=GroupRow)
def create_group(data: GroupCreate, db: Session = Depends(get_db)):
    return service.create_group(db, data.name)


@router.patch("/groups/{group_id}", response_model=GroupRow)
def update_group(group_id: str, data: GroupUpdate, db: Session = Depends(get_db)):
    return service.update_group(db, group_id, data.name, data.members)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: str, db: Session = Depends(get_db)):
    service.delete_group(db, group_id)


@router.get("/usage", response_model=UsageReport)
def usage_report(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return service.usage_report(db, days)
