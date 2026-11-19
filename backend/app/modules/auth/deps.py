"""Reusable FastAPI dependencies: who is calling, and are they allowed here?"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import read_token
from app.modules.auth.models import User
from app.modules.auth.service import user_apps


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise Unauthorized("Missing token")
    user = db.get(User, read_token(authorization[7:]))
    if not user or not user.is_active:
        raise Unauthorized("Unknown or disabled account")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise Forbidden("Admins only")
    return user


def require_app(app_name: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if app_name not in user_apps(user):
            raise Forbidden("You do not have access to this app")
        return user

    return dependency
