import datetime as dt

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import APPS, settings
from app.core.errors import BadRequest, Conflict, Invalid, NotFound
from app.core.utils import utcnow
from app.modules.admin.schemas import (AdminUserRow, BookRow, DailyOpens, GroupRow, InviteIn, Overview, PersonRef, ShareLabel,
                                       UsageBook, UsagePerson, UsageReport, UserPatch)
from app.modules.auth import groups as groups_service
from app.modules.auth.models import Group, Invite, User
from app.modules.auth.service import user_apps
from app.modules.library import service as library
from app.modules.transcription import service as transcription
from app.modules.usage import service as usage

ROLES = ("user", "admin")


def _clean_apps(apps: list[str]) -> list[str]:
    unknown = [a for a in apps if a not in APPS]
    if unknown:
        raise Invalid(f"Unknown app: {', '.join(unknown)}")
    return [a for a in APPS if a in apps]


def _row(user: User, doc_count: int) -> AdminUserRow:
    return AdminUserRow(id=user.id, email=user.email, role=user.role, apps=user_apps(user), is_active=user.is_active,
                        created_at=user.created_at, last_login_at=user.last_login_at, documents=doc_count)


def overview(db: Session) -> Overview:
    totals = library.totals(db)
    stt = transcription.totals(db)
    return Overview(
        users=db.scalar(select(func.count(User.id))) or 0,
        active_users=db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
        admins=db.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0,
        pending_invites=db.scalar(select(func.count(Invite.id)).where(Invite.used_at.is_(None))) or 0,
        documents=totals["documents"],
        notes=totals["notes"],
        transcriptions=stt["transcriptions"],
        minutes_transcribed=stt["minutes"],
    )


def list_users(db: Session) -> list[AdminUserRow]:
    counts = library.document_counts(db)
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [_row(u, counts.get(u.id, 0)) for u in users]


def update_user(db: Session, admin: User, user_id: str, patch: UserPatch) -> AdminUserRow:
    user = db.get(User, user_id)
    if not user:
        raise NotFound("Person not found")
    protected = user.email in settings.admin_emails
    if patch.role is not None:
        if patch.role not in ROLES:
            raise Invalid("Role must be user or admin")
        if patch.role != "admin" and (user.id == admin.id or protected):
            raise BadRequest("This admin cannot be demoted here (it is you, or the email is in ADMIN_EMAILS).")
        user.role = patch.role
    if patch.is_active is not None:
        if not patch.is_active and (user.id == admin.id or protected):
            raise BadRequest("This admin cannot be disabled here.")
        user.is_active = patch.is_active
    if patch.apps is not None:
        user.apps = _clean_apps(patch.apps)
    db.commit()
    return _row(user, library.document_counts(db).get(user.id, 0))


def list_invites(db: Session) -> list[Invite]:
    return list(db.scalars(select(Invite).where(Invite.used_at.is_(None)).order_by(Invite.created_at.desc())).all())


def create_invite(db: Session, admin: User, data: InviteIn) -> Invite:
    email = data.email.strip().lower()
    if "@" not in email:
        raise Invalid("Enter a valid email address")
    if data.role not in ROLES:
        raise Invalid("Role must be user or admin")
    if db.scalar(select(User).where(User.email == email)):
        raise Conflict("That person already has an account. Change their access in the People list.")
    invite = db.scalar(select(Invite).where(Invite.email == email))
    apps = _clean_apps(data.apps)
    if invite and invite.used_at is None:
        invite.apps, invite.role = apps, data.role  # update the pending invite
    elif invite:
        raise Conflict("That email was already used")
    else:
        invite = Invite(email=email, apps=apps, role=data.role, created_by=admin.id)
        db.add(invite)
    db.commit()
    return invite


def delete_invite(db: Session, invite_id: str) -> None:
    invite = db.get(Invite, invite_id)
    if not invite:
        raise NotFound("Invite not found")
    db.delete(invite)
    db.commit()


# ---------- books: who owns them and who may read them ----------
def _book_rows(db: Session, docs) -> list[BookRow]:
    if not docs:
        return []
    shares = library.shares_for(db, [d.id for d in docs])
    group_names = {g.id: g.name for g in groups_service.list_groups(db)}
    wanted_users = {d.user_id for d in docs} | {t for pairs in shares.values() for k, t in pairs if k == "user"}
    emails = {u.id: u.email for u in db.scalars(select(User).where(User.id.in_(wanted_users))).all()}
    opens = usage.opens_by_document(db)
    rows = []
    for d in docs:
        labels = []
        for kind, target in sorted(shares.get(d.id, [])):
            if kind == "all":
                labels.append(ShareLabel(kind="all", label="Everyone"))
            elif kind == "group" and target in group_names:
                labels.append(ShareLabel(kind="group", label=f"Group: {group_names[target]}"))
            elif kind == "user" and target in emails:
                labels.append(ShareLabel(kind="user", label=emails[target]))
        n, readers = opens.get(d.id, (0, 0))
        pairs = shares.get(d.id, [])
        rows.append(BookRow(id=d.id, title=d.title, size=d.size, created_at=d.created_at, owner_email=emails.get(d.user_id, "?"),
                            shared_with=labels, everyone=any(k == "all" for k, _ in pairs),
                            group_ids=[t for k, t in pairs if k == "group"], user_ids=[t for k, t in pairs if k == "user"],
                            opens=n, readers=readers))
    return rows


def list_books(db: Session) -> list[BookRow]:
    return _book_rows(db, library.list_all_documents(db))


async def create_book(db: Session, admin: User, file: UploadFile) -> BookRow:
    doc = await library.create_document(db, admin, file)
    return _book_rows(db, [doc])[0]


def share_book(db: Session, doc_id: str, everyone: bool, group_ids: list[str], user_ids: list[str]) -> BookRow:
    valid_groups = list(db.scalars(select(Group.id).where(Group.id.in_(group_ids))).all()) if group_ids else []
    valid_users = list(db.scalars(select(User.id).where(User.id.in_(user_ids))).all()) if user_ids else []
    library.set_shares(db, doc_id, everyone, valid_groups, valid_users)
    return _book_rows(db, [d for d in library.list_all_documents(db) if d.id == doc_id])[0]


def delete_book(db: Session, doc_id: str) -> None:
    library.delete_any_document(db, doc_id)


# ---------- groups ----------
def _group_rows(db: Session) -> list[GroupRow]:
    members = groups_service.members_by_group(db)
    return [GroupRow(id=g.id, name=g.name, members=[PersonRef(id=u.id, email=u.email) for u in members.get(g.id, [])])
            for g in groups_service.list_groups(db)]


def list_groups(db: Session) -> list[GroupRow]:
    return _group_rows(db)


def create_group(db: Session, name: str) -> GroupRow:
    group = groups_service.create_group(db, name)
    return next(r for r in _group_rows(db) if r.id == group.id)


def update_group(db: Session, group_id: str, name, members) -> GroupRow:
    groups_service.update_group(db, group_id, name, members)
    return next(r for r in _group_rows(db) if r.id == group_id)


def delete_group(db: Session, group_id: str) -> None:
    library.remove_group_shares(db, group_id)
    groups_service.delete_group(db, group_id)


# ---------- usage report ----------
def usage_report(db: Session, days: int) -> UsageReport:
    report = usage.report(db, days)
    stt = transcription.usage_by_user(db, report["since"])
    user_ids = {p["user_id"] for p in report["people"]} | set(stt)
    emails = {u.id: u.email for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    titles = library.titles_for(db, [b["id"] for b in report["top_books"]])

    seen = {p["user_id"]: p for p in report["people"]}
    people = []
    for uid in list(seen) + [u for u in stt if u not in seen]:
        entry = seen.get(uid, {"events": 0, "last_active": None})
        recordings, minutes = stt.get(uid, (0, 0))
        people.append(UsagePerson(user_id=uid, email=emails.get(uid, "?"), events=entry["events"], last_active=entry["last_active"],
                                  recordings=recordings, minutes=minutes))
    people.sort(key=lambda p: (p.events + p.recordings), reverse=True)
    return UsageReport(
        days=report["days"], opens=report["opens"], active_people=len(people),
        recordings=sum(n for n, _ in stt.values()), minutes=sum(m for _, m in stt.values()),
        daily=[DailyOpens(**d) for d in report["daily"]],
        top_books=[UsageBook(id=b["id"], title=titles.get(b["id"], "(deleted book)"), opens=b["opens"], readers=b["readers"]) for b in report["top_books"]],
        people=people,
    )
