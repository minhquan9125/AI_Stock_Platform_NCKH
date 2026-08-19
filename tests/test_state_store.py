import json
from storage.state_store import StateStore


def test_successful_retry_is_removed_from_failed_ledger(tmp_path):
    state = StateStore(tmp_path / "FPT")
    url = "https://cafef.vn/retry.chn"
    state.mark_failed(url, "timeout")
    assert url in state.failures

    state.mark_processed(url, "accepted")

    assert url not in state.failures
    rows = [
        json.loads(line)
        for line in state.failed_store.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all(item["url"] != url for item in rows)
