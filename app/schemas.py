from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    title: str
    url: str
    snippet: str
    score: float
    categories: list[str] = []


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[Document]
    summary: str | None = None


class CategoryCount(BaseModel):
    category: str
    count: int


class UserCredentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class MeResponse(BaseModel):
    id: int
    username: str
    role: str


class SearchLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    results_count: int
    created_at: datetime


class AdminSearchLogEntry(BaseModel):
    id: int
    username: str
    role: str
    query: str
    results_count: int
    created_at: datetime


class SavedArticleCreate(BaseModel):
    article_url: str
    article_title: str


class SavedArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_url: str
    article_title: str
    saved_at: datetime


class UserAdminResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime


class RoleChangeRequest(BaseModel):
    role: str


class TopQueryStat(BaseModel):
    query: str
    count: int


class AboveAverageUserStat(BaseModel):
    username: str
    searches: int


class StatsResponse(BaseModel):
    top_queries: list[TopQueryStat]
    users_above_average: list[AboveAverageUserStat]
