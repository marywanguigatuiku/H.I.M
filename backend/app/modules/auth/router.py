from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth import service
from app.modules.auth.deps import current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import AuthOut, Credentials, MeOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
def register(creds: Credentials, db: Session = Depends(get_db)):
    return service.register(db, creds)


@router.post("/login", response_model=AuthOut)
def login(creds: Credentials, db: Session = Depends(get_db)):
    return service.login(db, creds)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)):
    return service.me(user)
