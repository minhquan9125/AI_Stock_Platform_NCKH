"""Hợp đồng cho mọi nguồn bài viết."""
from abc import ABC, abstractmethod
from models import RawArticle


class BaseArticleCrawler(ABC):
    source_name: str

    @abstractmethod
    def search_articles(self, ticker: str, queries: list[str], max_pages: int, limit: int | None = None) -> list[str]: ...

    @abstractmethod
    def parse_article(self, url: str) -> RawArticle: ...
