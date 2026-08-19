"""Mô hình dữ liệu xuyên suốt pipeline."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RawArticle(BaseModel):
    source_name: str
    source_url: str
    canonical_url: str
    title: str = ""
    summary: str | None = None
    content: str = ""
    published_at: datetime | None = None
    published_at_raw: str | None = None
    author: str | None = None
    category: str | None = None
    thumbnail_url: str | None = None
    raw_html: str | None = Field(default=None, exclude=True)


class ArticleRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: str
    ticker: list[str]
    company_name: str | None
    title: str
    summary: str | None
    content: str
    published_at: datetime | None
    published_at_raw: str | None
    crawled_at: datetime
    source_name: str
    source_url: str
    canonical_url: str
    author: str | None
    category: str | None
    thumbnail_url: str | None
    language: str = "vi"
    document_type: str = "UNKNOWN"
    event_types: list[str] = Field(default_factory=list)
    matched_aliases: list[str] = Field(default_factory=list)
    relevance_score: float = 0
    relevance_reasons: list[str] = Field(default_factory=list)
    content_hash: str
    word_count: int
    status: str = "accepted"
