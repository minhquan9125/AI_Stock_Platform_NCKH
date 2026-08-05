from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ReportCandidate(BaseModel):
    title: str
    ticker: list[str] = Field(default_factory=list)
    source_platform: str
    source_page_url: str
    canonical_source_url: str
    broker: str | None = None
    published_at: datetime | None = None
    published_at_raw: str | None = None
    report_type: str = "OTHER"
    analyst: list[str] = Field(default_factory=list)
    description: str | None = None
    pdf_url: str | None = None
    page_text: str = ""


class ReportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_id: str
    ticker: list[str]
    company_name: str | None
    title: str
    description: str | None = None
    report_type: str
    broker: str | None
    source_platform: str
    published_at: datetime | None
    published_at_raw: str | None
    analyst: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    recommendation_raw: str | None = None
    target_price: float | None = None
    target_price_currency: str = "VND"
    current_price: float | None = None
    upside_percent: float | None = None
    valuation_methods: list[str] = Field(default_factory=list)
    source_page_url: str
    canonical_source_url: str
    mirror_urls: list[str] = Field(default_factory=list)
    pdf_url: str | None = None
    local_pdf_path: str | None = None
    pdf_hash: str | None = None
    extracted_text_path: str | None = None
    content_hash: str | None = None
    page_count: int | None = None
    language: str = "vi"
    crawled_at: datetime
    status: str = "accepted"
    validation_notes: list[str] = Field(default_factory=list)
