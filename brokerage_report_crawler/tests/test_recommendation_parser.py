from processing.recommendation_parser import parse_recommendation


def test_vietnamese_recommendation_and_prices():
    result = parse_recommendation("Khuyến nghị MUA. Giá mục tiêu: 101.600 đồng. Giá thị trường: 90.000 đồng. Tiềm năng tăng giá: 12,9%")
    assert result.recommendation == "BUY"
    assert result.raw == "MUA"
    assert result.target_price == 101600
    assert result.current_price == 90000
    assert result.upside_percent == 12.9


def test_unknown_recommendation_is_null():
    assert parse_recommendation("Không đưa ra đánh giá").recommendation is None


def test_tp_does_not_match_inside_another_word():
    result = parse_recommendation("LNST-CĐTS đạt 10.662 tỷ. Giá mục tiêu 94,500 đồng.")
    assert result.target_price == 94500


def test_first_prominent_recommendation_wins():
    result = parse_recommendation("MUA - Giá mục tiêu 95.400 đồng. Phần lịch sử từng khuyến nghị TÍCH LŨY.")
    assert result.recommendation == "BUY"
