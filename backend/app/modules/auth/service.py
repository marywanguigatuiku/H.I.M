import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APPS, settings
from app.core.errors import Conflict, Forbidden, Invalid, Unauthorized
from app.core.security import hash_password, make_token, verify_password
from app.core.utils import utcnow
from app.modules.auth.models import Invite, User
from app.modules.auth.schemas import AuthOut, Credentials, MeOut, UserOut

HOMES = {"library": "/", "transcribe": "/transcribe/"}


def user_apps(user: User) -> list[str]:
    """Admins can open every app; everyone else only the apps they were given."""
    if user.role == "admin":
        return list(APPS)
    return [a for a in APPS if a in (user.apps or [])]


def home_for(user: User) -> str:
    if user.role == "admin":
        return "/admin/"
    for app in APPS:
        if app in user_apps(user):
            return HOMES[app]
    return "/"


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, role=user.role, apps=user_apps(user), is_active=user.is_active)


def me(user: User) -> MeOut:
    return MeOut(user=user_out(user), home=home_for(user))


def _auth_out(user: User) -> AuthOut:
    return AuthOut(token=make_token(user.id), user=user_out(user), home=home_for(user))


def register(db: Session, creds: Credentials) -> AuthOut:
    email = creds.email.strip().lower()
    if len(creds.password) < 8 or "@" not in email:
        raise Invalid("Use a valid email and a password of 8+ characters")
    if db.scalar(select(User).where(User.email == email)):
        raise Conflict("Email already registered")

    role, apps = "user", list(settings.default_apps)
    invite = db.scalar(select(Invite).where(Invite.email == email, Invite.used_at.is_(None)))
    if invite:
        role, apps = invite.role, list(invite.apps or [])
        invite.used_at = utcnow()
    elif email in settings.admin_emails:
        pass  # promoted below
    elif not (settings.invite_code and hmac.compare_digest(creds.invite_code.encode(), settings.invite_code.encode())):
        raise Forbidden("Invalid invite code")
    if email in settings.admin_emails:
        role = "admin"

    user = User(email=email, pw_hash=hash_password(creds.password), role=role, apps=apps)
    db.add(user)
    db.commit()
    return _auth_out(user)


def login(db: Session, creds: Credentials) -> AuthOut:
    user = db.scalar(select(User).where(User.email == creds.email.strip().lower()))
    if not user or not verify_password(creds.password, user.pw_hash):
        raise Unauthorized("Wrong email or password")
    if not user.is_active:
        raise Forbidden("This account has been disabled")
    if user.email in settings.admin_emails and user.role != "admin":
        user.role = "admin"
    user.last_login_at = utcnow()
    db.commit()
    return _auth_out(user)


def sync_admins(db: Session) -> None:
    """At startup, make sure everyone listed in ADMIN_EMAILS is an admin."""
    if not settings.admin_emails:
        return
    for user in db.scalars(select(User).where(User.email.in_(settings.admin_emails))).all():
        if user.role != "admin" or not user.is_active:
            user.role, user.is_active = "admin", True
    db.commit()
