from datetime import datetime, timezone

from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ROLE_READER = "reader"
ROLE_WRITER = "writer"
ROLE_OWNER = "owner"
ALL_ROLES = [ROLE_READER, ROLE_WRITER, ROLE_OWNER]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    role: Mapped["Role"] = relationship(back_populates="users")
    search_logs: Mapped[list["SearchLog"]] = relationship(back_populates="user")
    saved_articles: Mapped[list["SavedArticle"]] = relationship(back_populates="user")


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="search_logs")


class SavedArticle(Base):
    __tablename__ = "saved_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    article_url: Mapped[str] = mapped_column(String(500), nullable=False)
    article_title: Mapped[str] = mapped_column(String(300), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="saved_articles")


def seed_roles(db) -> None:
    existing = {r.name for r in db.query(Role).all()}
    for name in ALL_ROLES:
        if name not in existing:
            db.add(Role(name=name))
    db.commit()
