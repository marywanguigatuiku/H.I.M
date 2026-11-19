import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.storage import get_storage
from app.modules.auth.deps import require_app
from app.modules.auth.models import User
from app.modules.library import service
from app.modules.library.schemas import DocumentOut, NoteIn, NoteOut, ProgressIn

router = APIRouter(prefix="/api", tags=["library"])
library_user = require_app("library")


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: User = Depends(library_user), db: Session = Depends(get_db)):
    return service.list_documents(db, user)


@router.post("/documents", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), user: User = Depends(library_user), db: Session = Depends(get_db)):
    doc = await service.create_document(db, user, file)
    return service.to_out(db, user, doc)


@router.get("/documents/{doc_id}/file")
def download_document(doc_id: str, user: User = Depends(library_user), db: Session = Depends(get_db)):
    return get_storage().response(service.file_key_for_download(db, user, doc_id), "application/pdf")


@router.post("/documents/{doc_id}/opened", status_code=204)
def document_opened(doc_id: str, user: User = Depends(library_user), db: Session = Depends(get_db)):
    service.mark_opened(db, user, doc_id)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str, user: User = Depends(library_user), db: Session = Depends(get_db)):
    service.delete_document(db, user, doc_id)


@router.put("/documents/{doc_id}/progress", response_model=DocumentOut)
def save_progress(doc_id: str, p: ProgressIn, user: User = Depends(library_user), db: Session = Depends(get_db)):
    return service.save_progress(db, user, doc_id, p)


@router.put("/notes/{note_id}", response_model=NoteOut)
def upsert_note(note_id: str, n: NoteIn, user: User = Depends(library_user), db: Session = Depends(get_db)):
    return service.upsert_note(db, user, note_id, n)


@router.get("/notes", response_model=list[NoteOut])
def pull_notes(since: Optional[dt.datetime] = None, user: User = Depends(library_user), db: Session = Depends(get_db)):
    return service.pull_notes(db, user, since)
