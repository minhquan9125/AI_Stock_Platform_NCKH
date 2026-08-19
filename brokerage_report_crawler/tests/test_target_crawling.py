from types import SimpleNamespace

from config.settings import Settings
from crawlers.ssi import SSICrawler
from models import ReportCandidate
from services.crawl_service import CrawlService
from storage.jsonl_store import JsonlStore
from main import parser


COMPANIES = {
    "FPT": {
        "company_name": "Công ty Cổ phần FPT",
        "positive_aliases": ["Tập đoàn FPT", "cổ phiếu FPT"],
        "excluded_entities": {},
    }
}


class FakeCrawler:
    source_platform = "Fixture"
    official_broker = None

    def __init__(self, count=5, exhausted=True):
        self.count = count
        self.exhausted = exhausted
        self.calls = 0

    def search_reports(self, ticker, max_pages, target_reports):
        self.calls += 1
        return [
            ReportCandidate(
                title=f"FPT - Báo cáo chuyên đề số {index}", ticker=[ticker],
                source_platform=self.source_platform,
                source_page_url=f"https://fixture.test/{index}",
                canonical_source_url=f"https://fixture.test/{index}",
                broker=f"BROKER{index}",
                page_text=f"Tập đoàn FPT cổ phiếu FPT nội dung riêng biệt {index}",
            )
            for index in range(self.count)
        ]

    def fetch_detail(self, candidate):
        return candidate


def service(tmp_path, crawler):
    settings = Settings(data_dir=tmp_path, workers=3, near_duplicate_threshold=100)
    return CrawlService({"fixture": crawler}, None, settings, COMPANIES)


def test_target_collects_unique_accepted_and_stops(tmp_path):
    crawler = FakeCrawler(count=6)
    result = service(tmp_path, crawler).run(
        "FPT", ["fixture"], target_reports=3, download_pdf=False,
        extract_text=False, workers=3, progress=None,
    )
    assert result.target == 3
    assert result.new_accepted == 3
    assert result.total_unique_reports == 3


def test_existing_reports_count_toward_target(tmp_path):
    crawler = FakeCrawler(count=10)
    store = JsonlStore(tmp_path / "cleaned/FPT/FPT_brokerage_reports.jsonl")
    store.append({"report_id": "old-1", "title": "old"})
    store.append({"report_id": "old-2", "title": "old"})
    result = service(tmp_path, crawler).run(
        "FPT", ["fixture"], target_reports=2, download_pdf=False,
        extract_text=False, progress=None,
    )
    assert crawler.calls == 0
    assert result.existing_reports == 2
    assert result.new_accepted == 0
    assert result.total_unique_reports == 2


def test_source_exhaustion_is_reported_before_target(tmp_path):
    crawler = FakeCrawler(count=1, exhausted=True)
    result = service(tmp_path, crawler).run(
        "FPT", ["fixture"], target_reports=5, download_pdf=False,
        extract_text=False, progress=None,
    )
    assert result.total_unique_reports == 1
    assert result.exhausted_sources == ["fixture"]


def test_failed_download_does_not_count_toward_target(tmp_path):
    crawler = FakeCrawler(count=1)
    crawler.fetch_detail = lambda candidate: (_ for _ in ()).throw(RuntimeError("download_failed"))
    result = service(tmp_path, crawler).run(
        "FPT", ["fixture"], target_reports=5, download_pdf=False,
        extract_text=False, progress=None,
    )
    assert result.failed == 1
    assert result.new_accepted == 0
    assert result.total_unique_reports == 0


def test_default_cli_sources_are_stable_aggregators_only():
    args = parser().parse_args(["--ticker", "FPT"])
    assert args.sources == ["cafef", "vietstock"]


class PageClient:
    def __init__(self):
        self.calls = 0

    def get(self, url):
        self.calls += 1
        html = """
        <div class="chart__content__item">
          <a class="titlePost">FPT - Báo cáo cập nhật</a>
          <div class="chart__content__item__time"><span>01/01/2026</span>
            <a href="https://ssi.com.vn/fpt.pdf">Tải</a></div>
        </div>
        """
        return SimpleNamespace(text=html)


def test_auto_pagination_stops_after_two_pages_without_new_urls():
    client = PageClient()
    crawler = SSICrawler(client)
    rows = crawler.search_reports("FPT", max_pages=20, target_reports=None)
    assert len(rows) == 1
    assert crawler.pages_scanned == 3
    assert crawler.exhausted
