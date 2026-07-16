from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import os

from app.summarizer import summarize as make_summary
from app.db import Base, engine, get_db
from app.models import Role, User, SearchLog, seed_roles, ROLE_READER
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.schemas import Document, SearchResponse, UserCredentials, TokenResponse, MeResponse, CategoryCount
from app.routers import history, saved, admin

load_dotenv()

Base.metadata.create_all(bind=engine)
with Session(engine) as _startup_db:
    seed_roles(_startup_db)

app = FastAPI(
    title="Searcher API",
    description="RAG-based document search over Wikipedia articles",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history.router)
app.include_router(saved.router)
app.include_router(admin.router)

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
es = Elasticsearch(ES_URL)
INDEX = "articles"

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "elasticsearch": es.ping()}


@app.post("/auth/register", response_model=TokenResponse, tags=["auth"])
def register(credentials: UserCredentials, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == credentials.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")

    reader_role = db.query(Role).filter(Role.name == ROLE_READER).first()
    user = User(
        username=credentials.username,
        password_hash=hash_password(credentials.password),
        role_id=reader_role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, role=user.role.name)


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(credentials: UserCredentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, role=user.role.name)


@app.get("/me", response_model=MeResponse, tags=["auth"])
def me(user: User = Depends(get_current_user)):
    return MeResponse(id=user.id, username=user.username, role=user.role.name)


@app.get("/categories", response_model=list[CategoryCount], tags=["search"])
def list_categories(user: User = Depends(get_current_user)):
    """Distinct Wikipedia categories present in the index, for the search filter dropdown."""
    if not es.ping():
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable")

    resp = es.search(
        index=INDEX,
        size=0,
        aggs={"categories": {"terms": {"field": "categories", "size": 50}}},
    )
    buckets = resp["aggregations"]["categories"]["buckets"]
    return [CategoryCount(category=b["key"], count=b["doc_count"]) for b in buckets]


@app.get("/search", response_model=SearchResponse, tags=["search"])
def search(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
    with_summary: bool = Query(False, description="Summarize results with LLM"),
    category: str | None = Query(None, description="Filter results to this Wikipedia category"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not es.ping():
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable")

    query_clause = {
        "bool": {
            "must": {
                "multi_match": {
                    "query": q,
                    "fields": ["title^3", "content"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        }
    }
    if category:
        query_clause["bool"]["filter"] = {"term": {"categories": category}}

    resp = es.search(
        index=INDEX,
        query=query_clause,
        highlight={
            "fields": {
                "content": {
                    "fragment_size": 250,
                    "number_of_fragments": 1,
                    "pre_tags": [""],
                    "post_tags": [""],
                }
            }
        },
        size=top_k,
    )
    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]

    results = []
    for h in hits:
        src = h["_source"]
        if "highlight" in h and "content" in h["highlight"]:
            snippet = "...".join(h["highlight"]["content"])
        else:
            snippet = src["content"][:300]

        results.append(Document(
            title=src["title"],
            url=src["url"],
            snippet=snippet,
            score=round(h["_score"], 4),
            categories=src.get("categories", []),
        ))

    db.add(SearchLog(user_id=user.id, query=q, results_count=total))
    db.commit()

    summary = None
    if with_summary and results:
        context = "\n\n".join(f"[{r.title}]\n{r.snippet}" for r in results)
        summary = make_summary(q, context)

    return SearchResponse(query=q, total=total, results=results, summary=summary)
