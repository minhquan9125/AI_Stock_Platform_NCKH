from .cafef import CafeFCrawler
from .ssi import SSICrawler
from .vietstock import VietstockCrawler
from .vndirect import VNDirectCrawler

CRAWLERS = {
    "cafef": CafeFCrawler,
    "vietstock": VietstockCrawler,
    "ssi": SSICrawler,
    "vndirect": VNDirectCrawler,
}

__all__ = ["CRAWLERS", "CafeFCrawler", "VietstockCrawler", "SSICrawler", "VNDirectCrawler"]
