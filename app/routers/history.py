from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import SearchLog, User
from app.schemas import SearchLogEntry

router = APIRouter(tags=["history"])


@router.get("/history/me", response_model=list[SearchLogEntry])
def my_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == user.id)
        .order_by(SearchLog.created_at.desc())
        .all()
    )
    return logs
