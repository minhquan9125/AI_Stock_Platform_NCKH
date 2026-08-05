import json
from storage.state_store import StateStore


def test_resume_and_resolved_retry(tmp_path):
    state = StateStore(tmp_path / "FPT" / "vietstock")
    url = "https://finance.vietstock.vn/downloadedoc/1"
    state.fail(url, "timeout")
    assert url in StateStore(state.root).failures
    state.success(url, "accepted")
    loaded = StateStore(state.root)
    assert url in loaded.processed
    assert url not in loaded.failures
    rows = [json.loads(line) for line in loaded.failed_store.path.read_text(encoding="utf-8").splitlines() if line]
    assert rows == []
