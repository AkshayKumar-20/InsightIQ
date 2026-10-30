from app import analytics

def test_summary_and_product(db_path):
    s = analytics.summary(db_path)
    assert s["revenue"] == 69
    assert s["transactions"] == 3
    assert analytics.products(db_path)[0]["product"] == "Alpha"

def test_trends_and_regions(db_path):
    assert [r["month"] for r in analytics.trends(db_path)] == ["2026-01", "2026-02"]
    assert analytics.regions(db_path)[0]["region"] == "North"

def test_comparison_and_zero_baseline(db_path):
    p = analytics.comparison("2026-01", "2026-02", db_path)
    assert p["absolute_change"] == -29
    assert p["percentage_change"] == round(-29 / 49 * 100, 2)
    z = analytics.comparison("2025-01", "2026-01", db_path)
    assert z["percentage_change"] is None
