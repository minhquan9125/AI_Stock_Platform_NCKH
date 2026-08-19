from processing.relevance import calculate_relevance

LONG = ("FPT công bố doanh thu lợi nhuận tăng 20% và nhà đầu tư quan tâm cổ phiếu. " * 30)


def test_clear_fpt_analysis_is_accepted():
    result = calculate_relevance("FPT", "Công ty Cổ phần FPT", ["FPT", "Tập đoàn FPT", "cổ phiếu FPT"], "Phân tích cổ phiếu FPT", "FPT tăng trưởng", LONG)
    assert result.accepted and result.score >= 5


def test_single_weak_mention_scores_low():
    text = ("Thị trường có nhiều diễn biến chung và thanh khoản thay đổi. " * 30) + " FPT."
    result = calculate_relevance("FPT", None, ["FPT"], "Tin thị trường", "", text)
    assert not result.accepted


def test_many_tickers_penalty():
    text = LONG + " AAA BBB CCC DDD EEE GGG HHH KKK"
    result = calculate_relevance("FPT", None, ["FPT"], "FPT trên thị trường", "", text)
    assert "many_tickers:-3" in result.reasons


def test_ticker_boundary():
    result = calculate_relevance("FPT", None, ["FPT"], "AFPTX ra mắt", "", "AFPTX " * 200)
    assert not result.matched_aliases


def test_rejects_fpt_retail_when_target_is_fpt_corporation():
    text = ("Công ty Cổ phần Bán lẻ Kỹ thuật số FPT (HoSE: FRT) công bố doanh thu lợi nhuận tăng 20%. " * 25)
    result = calculate_relevance("FPT", "Công ty Cổ phần FPT", ["FPT", "Tập đoàn FPT"], "Doanh thu FPT Retail tăng mạnh", "", text)
    assert not result.accepted
    assert any(reason.startswith("other_explicit_ticker:-7") for reason in result.reasons)


EXCLUDED = {
    "FPT Retail": "FRT",
    "FPT Telecom": "FOX",
    "FPT Online": "FOC",
    "Chứng khoán FPT": "FTS",
}
POSITIVE = ["Tập đoàn FPT", "FPT Corporation", "Công ty Cổ phần FPT", "cổ phiếu FPT", "mã FPT", "HoSE: FPT"]


def evaluate_fpt(title: str, content: str):
    return calculate_relevance(
        "FPT", "Công ty Cổ phần FPT", ["FPT", *POSITIVE], title, "",
        content, positive_aliases=POSITIVE, excluded_entities=EXCLUDED,
    )


def test_fpt_retail_is_excluded():
    result = evaluate_fpt("FPT Retail báo lãi lớn", "FPT Retail (HoSE: FRT) công bố doanh thu lợi nhuận. " * 30)
    assert not result.accepted and result.excluded_matches == ["FPT Retail"]


def test_fpt_telecom_is_excluded():
    result = evaluate_fpt("FPT Telecom tăng trưởng", "FPT Telecom (UPCoM: FOX) ghi nhận doanh thu. " * 30)
    assert not result.accepted and "FPT Telecom" in result.excluded_matches


def test_fpt_online_is_excluded():
    result = evaluate_fpt("FPT Online chia cổ tức", "FPT Online (UPCoM: FOC) công bố cổ tức. " * 30)
    assert not result.accepted and "FPT Online" in result.excluded_matches


def test_fpt_securities_is_excluded():
    result = evaluate_fpt("Chứng khoán FPT báo lãi", "Chứng khoán FPT (HoSE: FTS) công bố lợi nhuận. " * 30)
    assert not result.accepted and "Chứng khoán FPT" in result.excluded_matches


def test_fpt_group_is_accepted():
    result = evaluate_fpt("Tập đoàn FPT tăng trưởng hai chữ số", "Tập đoàn FPT công bố doanh thu lợi nhuận tăng 20%. " * 30)
    assert result.accepted


def test_hose_fpt_is_accepted():
    result = evaluate_fpt("Cổ phiếu công nghệ tăng trưởng", "Công ty công nghệ niêm yết HoSE: FPT công bố doanh thu lợi nhuận. " * 30)
    assert result.accepted


def test_excluded_subsidiary_allowed_only_with_clear_parent_analysis():
    result = evaluate_fpt(
        "Tập đoàn FPT và hệ sinh thái",
        ("Tập đoàn FPT (HoSE: FPT) được phân tích ở cấp công ty mẹ. "
         "FPT Retail là một khoản đầu tư trong hệ sinh thái. Doanh thu lợi nhuận tăng 20%. ") * 20,
    )
    assert result.accepted


def test_multi_company_news_is_penalized():
    text = ("HoSE: FPT HoSE: HPG HoSE: VNM HoSE: VIC cùng xuất hiện trong bản tin thị trường. " * 30)
    result = evaluate_fpt("Nhiều cổ phiếu biến động", text)
    assert result.multi_company and "multi_company_news:-3" in result.reasons
