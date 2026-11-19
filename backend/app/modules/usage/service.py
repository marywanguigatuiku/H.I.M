import datetime as dt
from typing import Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.utils import utcnow
from app.modules.usage.models import UsageEvent


def record(db: Session, user_id: str, app: str, kind: str, ref_id: Optional[str] = None, throttle_minutes: int = 0) -> None:
    """Stores one event. With throttle_minutes the same person doing the same thing again soon is ignored."""
    if throttle_minutes:
        recent = db.scalar(select(UsageEvent.id).where(
            UsageEvent.user_id == user_id, UsageEvent.kind == kind, UsageEvent.ref_id == ref_id,
            UsageEvent.created_at > utcnow() - dt.timedelta(minutes=throttle_minutes)).limit(1))
        if recent is not None:
            return
    db.add(UsageEvent(user_id=user_id, app=app, kind=kind, ref_id=ref_id))
    db.commit()


def opens_by_document(db: Session) -> dict[str, tuple[int, int]]:
    """{book id: (times opened, different readers)} over all time."""
    rows = db.execute(select(UsageEvent.ref_id, func.count(UsageEvent.id), func.count(distinct(UsageEvent.user_id)))
                      .where(UsageEvent.kind == "document_open", UsageEvent.ref_id.is_not(None))
                      .group_by(UsageEvent.ref_id)).all()
    return {ref: (int(n), int(readers)) for ref, n, readers in rows}


def report(db: Session, days: int) -> dict:
    days = max(1, min(days, 365))
    since = utcnow() - dt.timedelta(days=days)
    opens = UsageEvent.kind == "document_open"

    per_day = {str(day): int(n) for day, n in db.execute(
        select(func.date(UsageEvent.created_at), func.count(UsageEvent.id))
        .where(opens, UsageEvent.created_at >= since).group_by(func.date(UsageEvent.created_at))).all()}
    today = utcnow().date()
    daily = [{"date": str(today - dt.timedelta(days=i)), "opens": per_day.get(str(today - dt.timedelta(days=i)), 0)}
             for i in range(days - 1, -1, -1)]

    top_books = [{"id": ref, "opens": int(n), "readers": int(readers)} for ref, n, readers in db.execute(
        select(UsageEvent.ref_id, func.count(UsageEvent.id), func.count(distinct(UsageEvent.user_id)))
        .where(opens, UsageEvent.created_at >= since, UsageEvent.ref_id.is_not(None))
        .group_by(UsageEvent.ref_id).order_by(func.count(UsageEvent.id).desc()).limit(10)).all()]

    people = [{"user_id": uid, "events": int(n), "last_active": last} for uid, n, last in db.execute(
        select(UsageEvent.user_id, func.count(UsageEvent.id), func.max(UsageEvent.created_at))
        .where(UsageEvent.created_at >= since).group_by(UsageEvent.user_id)
        .order_by(func.count(UsageEvent.id).desc()).limit(20)).all()]

    total_opens = int(db.scalar(select(func.count(UsageEvent.id)).where(opens, UsageEvent.created_at >= since)) or 0)
    return {"days": days, "since": since, "opens": total_opens, "daily": daily, "top_books": top_books, "people": people}
