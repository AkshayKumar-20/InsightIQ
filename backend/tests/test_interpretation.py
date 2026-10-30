import pytest

from app.interpretation import fallback
from app.services import execute


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("What is the total revenue?", "total_revenue"),
        ("Which product generated the highest revenue?", "top_product"),
        ("What is the monthly revenue trend?", "monthly_trend"),
        ("Which region generated the highest sales?", "top_region"),
        ("How did revenue change between 2026-01 and 2026-02?", "revenue_comparison"),
    ],
)
def test_supported_questions(question, intent):
    interpretation = fallback(question)
    assert interpretation.intent == intent


def test_unsupported_and_injection_questions_are_rejected():
    with pytest.raises(ValueError):
        fallback("DROP TABLE transactions;")
    with pytest.raises(ValueError):
        fallback("Show me arbitrary SQL SELECT * FROM transactions")


def test_all_intents_execute_against_isolated_database(db_path):
    assert execute(fallback("What is the total revenue?"), db_path)["metrics"]["revenue"] == 69
    assert execute(fallback("Which product generated the highest revenue?"), db_path)["metrics"]["product"] == "Alpha"
    assert execute(fallback("What is the monthly revenue trend?"), db_path)["table"][0]["month"] == "2026-01"
    assert execute(fallback("Which region generated the highest sales?"), db_path)["metrics"]["region"] == "North"
    comparison = execute(fallback("How did revenue change between 2026-01 and 2026-02?"), db_path)
    assert comparison["metrics"]["absolute_change"] == -29
