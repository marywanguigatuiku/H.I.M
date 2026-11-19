"""Groups of people. Used by the admin area, and by the library to find which books a person may see."""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid, NotFound
from app.modules.auth.models import Group, GroupMember, User


def group_ids_for(db: Session, user: User) -> list[str]:
    return list(db.scalars(select(GroupMember.group_id).where(GroupMember.user_id == user.id)).all())


def members_by_group(db: Session) -> dict[str, list[User]]:
    rows = db.execute(select(GroupMember.group_id, User).join(User, User.id == GroupMember.user_id).order_by(User.email)).all()
    out: dict[str, list[User]] = {}
    for group_id, user in rows:
        out.setdefault(group_id, []).append(user)
    return out


def list_groups(db: Session) -> list[Group]:
    return list(db.scalars(select(Group).order_by(Group.name)).all())


def create_group(db: Session, name: str) -> Group:
    name = name.strip()
    if not name or len(name) > 100:
        raise Invalid("Give the group a name (up to 100 characters)")
    if db.scalar(select(Group).where(Group.name == name)):
        raise Conflict("A group with that name already exists")
    group = Group(name=name)
    db.add(group)
    db.commit()
    return group


def update_group(db: Session, group_id: str, name: str | None, member_ids: list[str] | None) -> Group:
    group = db.get(Group, group_id)
    if not group:
        raise NotFound("Group not found")
    if name is not None:
        name = name.strip()
        if not name:
            raise Invalid("Give the group a name")
        clash = db.scalar(select(Group).where(Group.name == name, Group.id != group_id))
        if clash:
            raise Conflict("A group with that name already exists")
        group.name = name
    if member_ids is not None:
        valid = set(db.scalars(select(User.id).where(User.id.in_(member_ids))).all()) if member_ids else set()
        db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
        for uid in valid:
            db.add(GroupMember(group_id=group_id, user_id=uid))
    db.commit()
    return group


def delete_group(db: Session, group_id: str) -> None:
    group = db.get(Group, group_id)
    if not group:
        raise NotFound("Group not found")
    db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
    db.delete(group)
    db.commit()
