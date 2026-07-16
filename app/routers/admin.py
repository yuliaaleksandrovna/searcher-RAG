from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.models import Role, User, ROLE_OWNER, ALL_ROLES
from app.schemas import (
    AdminSearchLogEntry,
    StatsResponse,
    TopQueryStat,
    AboveAverageUserStat,
    UserAdminResponse,
    RoleChangeRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(ROLE_OWNER))])


# JOIN across search_logs -> users -> roles: every user's search history, not just the caller's own.
HISTORY_SQL = """
    SELECT sl.id AS id, u.username AS username, r.name AS role, sl.query AS query,
           sl.results_count AS results_count, sl.created_at AS created_at
    FROM search_logs sl
    JOIN users u ON u.id = sl.user_id
    JOIN roles r ON r.id = u.role_id
    ORDER BY sl.created_at DESC
"""

# GROUP BY: most frequent search terms across all users.
TOP_QUERIES_SQL = """
    SELECT query, COUNT(*) AS count
    FROM search_logs
    GROUP BY query
    ORDER BY count DESC
    LIMIT 10
"""

# JOIN + GROUP BY + subquery: users who search more often than the average user.
ABOVE_AVERAGE_SQL = """
    SELECT u.username AS username, COUNT(sl.id) AS searches
    FROM users u
    JOIN search_logs sl ON sl.user_id = u.id
    GROUP BY u.id, u.username
    HAVING COUNT(sl.id) > (
        SELECT AVG(cnt) FROM (
            SELECT COUNT(*) AS cnt FROM search_logs GROUP BY user_id
        )
    )
    ORDER BY searches DESC
"""


@router.get("/history", response_model=list[AdminSearchLogEntry])
def all_history(db: Session = Depends(get_db)):
    rows = db.execute(text(HISTORY_SQL)).mappings().all()
    return [AdminSearchLogEntry(**row) for row in rows]


@router.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)):
    top_queries = db.execute(text(TOP_QUERIES_SQL)).mappings().all()
    above_average = db.execute(text(ABOVE_AVERAGE_SQL)).mappings().all()
    return StatsResponse(
        top_queries=[TopQueryStat(**row) for row in top_queries],
        users_above_average=[AboveAverageUserStat(**row) for row in above_average],
    )


@router.get("/users", response_model=list[UserAdminResponse])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).join(Role).order_by(User.id).all()
    return [
        UserAdminResponse(
            id=u.id, username=u.username, role=u.role.name, created_at=u.created_at
        )
        for u in users
    ]


@router.patch("/users/{user_id}/role", response_model=UserAdminResponse)
def change_role(user_id: int, payload: RoleChangeRequest, db: Session = Depends(get_db)):
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ALL_ROLES}")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.query(Role).filter(Role.name == payload.role).first()
    user.role_id = role.id
    db.commit()
    db.refresh(user)
    return UserAdminResponse(
        id=user.id, username=user.username, role=user.role.name, created_at=user.created_at
    )
