from app import analytics
from app.database import connect, initialize
from app.generic import answer, activate, ingest_generic


def test_region_results_keep_the_region_label(db_path):
    rows = analytics.regions(db_path)

    assert rows[0]["region"] in {"North", "South"}
    assert rows[0]["region"] != "nan"
    assert rows[0]["region"] is not None


def test_conversation_messages_are_returned_in_insert_order(tmp_path):
    db = tmp_path / "conversation.sqlite3"
    initialize(db)
    with connect(db) as connection:
        conversation_id = connection.execute(
            "INSERT INTO conversations(title) VALUES (?)", ("Test",)
        ).lastrowid
        connection.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, "user", "First question"),
        )
        connection.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, "assistant", "First answer"),
        )
        connection.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, "user", "Second question"),
        )
        connection.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, "assistant", "Second answer"),
        )
        messages = connection.execute(
            "SELECT role, content FROM messages "
            "WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        ).fetchall()

    assert [(row["role"], row["content"]) for row in messages] == [
        ("user", "First question"),
        ("assistant", "First answer"),
        ("user", "Second question"),
        ("assistant", "Second answer"),
    ]


def test_generic_queries_use_the_selected_dataset_not_the_latest_one(tmp_path):
    db = tmp_path / "datasets.sqlite3"
    initialize(db)
    first = tmp_path / "first.csv"
    first.write_text("Region,Sales\nNorth,10\n", encoding="utf-8")
    second = tmp_path / "second.csv"
    second.write_text("Region,Sales\nSouth,99\n", encoding="utf-8")

    ingest_generic(first, db)
    first_dataset = activate(db)
    ingest_generic(second, db)
    second_dataset = activate(db)

    first_result = answer(
        "Which region has the highest sales?",
        db_path=db,
        dataset_ref=f"generic:{first_dataset['id']}",
    )
    second_result = answer(
        "Which region has the highest sales?",
        db_path=db,
        dataset_ref=f"generic:{second_dataset['id']}",
    )

    assert first_result["table"][0]["group_value"] == "North"
    assert second_result["table"][0]["group_value"] == "South"
