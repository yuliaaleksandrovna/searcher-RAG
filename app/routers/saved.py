from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.db import get_db
from app.models import SavedArticle, User, ROLE_WRITER, ROLE_OWNER
from app.schemas import SavedArticleCreate, SavedArticleResponse

router = APIRouter(tags=["saved"])


@router.post("/saved", response_model=SavedArticleResponse, status_code=status.HTTP_201_CREATED)
def save_article(
    payload: SavedArticleCreate,
    user: User = Depends(require_role(ROLE_WRITER, ROLE_OWNER)),
    db: Session = Depends(get_db),
):
    entry = SavedArticle(
        user_id=user.id,
        article_url=payload.article_url,
        article_title=payload.article_title,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/saved", response_model=list[SavedArticleResponse])
def list_saved(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SavedArticle)
        .filter(SavedArticle.user_id == user.id)
        .order_by(SavedArticle.saved_at.desc())
        .all()
    )


@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved(
    saved_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.get(SavedArticle, saved_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Saved article not found")
    if entry.user_id != user.id and user.role.name != ROLE_OWNER:
        raise HTTPException(status_code=403, detail="Not allowed to delete this entry")
    db.delete(entry)
    db.commit()
