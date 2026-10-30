import pytest

from app.generic import answer, activate, ingest_generic


def test_pesticide_schema_is_profiled_and_queryable(tmp_path):
    db = tmp_path / "pesticides.sqlite3"
    csv = tmp_path / "pesticides.csv"
    csv.write_text(
        "Pesticide,Manufacturer,Price,Expiry_Date\n"
        "NeemGuard,Agro Labs,120.50,2027-01-01\n"
        "CropSafe,Agro Labs,,2026-06-30\n"
        "FieldShield,Green Co,95.00,2026-06-30\n"
        "FieldShield,Green Co,95.00,2026-06-30\n",
        encoding="utf-8",
    )

    ingest_generic(csv, db)
    profile = activate(db)

    assert profile["filename"] == "pesticides.csv"
    assert profile["row_count"] == 4
    assert profile["column_count"] == 4
    assert profile["missing_values"] == 1
    assert profile["duplicate_rows"] == 1
    assert {column["type"] for column in profile["columns"]} >= {"number", "categorical", "date"}
    assert answer("What is the average price?", db_path=db)["metrics"]["column"] == "Price"


def test_employee_schema_is_kept_separate_from_pesticide_schema(tmp_path):
    db = tmp_path / "employees.sqlite3"
    csv = tmp_path / "employees.csv"
    csv.write_text(
        "Employee_Name,Department,Salary,Joining_Date\n"
        "Asha,Engineering,80000,2025-01-10\n"
        "Ravi,Sales,65000,2024-03-15\n",
        encoding="utf-8",
    )

    ingest_generic(csv, db)
    profile = activate(db)

    assert profile["filename"] == "employees.csv"
    assert [column["label"] for column in profile["columns"]] == [
        "Employee_Name",
        "Department",
        "Salary",
        "Joining_Date",
    ]
    result = answer("What is the highest salary?", db_path=db)
    assert result["metrics"]["column"] == "Salary"
    assert result["metrics"]["value"] == 80000


def test_invalid_csv_is_rejected_with_a_clear_error(tmp_path):
    csv = tmp_path / "invalid.csv"
    csv.write_bytes(b"\xff\xfe\x00\x00")

    with pytest.raises(ValueError):
        ingest_generic(csv, tmp_path / "invalid.sqlite3")


def test_natural_language_operations_use_schema_and_context(tmp_path):
    db = tmp_path / "questions.sqlite3"
    csv = tmp_path / "employees.csv"
    csv.write_text(
        "Employee_Name,Department,Salary,Joining_Date\n"
        "Asha,Engineering,80000,2025-01-10\n"
        "Ravi,Sales,65000,2024-03-15\n"
        "Mina,Engineering,90000,2025-06-20\n"
        "Dev,Sales,55000,2025-07-01\n",
        encoding="utf-8",
    )
    ingest_generic(csv, db)
    activate(db)

    assert answer("count", db_path=db)["metrics"]["matching_rows"] == 4
    assert answer("how many records?", db_path=db)["metrics"]["matching_rows"] == 4
    assert answer("average salary", db_path=db)["metrics"]["value"] == 72500
    assert answer("highest salary", db_path=db)["metrics"]["value"] == 90000
    assert answer("which department has more employees?", db_path=db)["table"][0]["group_value"] == "Engineering"
    assert len(answer("give me the top five", db_path=db)["table"]) == 4
    assert answer("what happened in 2025?", db_path=db)["metrics"]["matching_rows"] == 3
    assert len(answer("show the first two rows", db_path=db)["table"]) == 2
    assert answer("how many unique departments?", db_path=db)["metrics"]["unique_values"] == 2
    assert len(answer("show Sales", db_path=db)["table"]) == 2
    comparison = answer("compare 2024 and 2025 salary", db_path=db)
    assert comparison["metrics"]["2024"] == 65000
    assert comparison["metrics"]["2025"] == 225000


def test_follow_up_questions_keep_operation_and_entity_context(tmp_path):
    db = tmp_path / "followups.sqlite3"
    csv = tmp_path / "sales.csv"
    csv.write_text(
        "Region,Sales,Transaction_Date\n"
        "South,100,2025-01-01\n"
        "North,70,2025-01-02\n"
        "North,30,2025-01-03\n",
        encoding="utf-8",
    )
    ingest_generic(csv, db)
    activate(db)

    first = answer("Which region has the highest sales?", db_path=db)
    context = {
        "question": "Which region has the highest sales?",
        "group_column": first["metrics"]["group_column"],
        "column": first["metrics"]["column"],
        "selected_group": first["metrics"]["selected_group"],
        "entities": [{"column": first["metrics"]["group_column"], "value": first["metrics"]["selected_group"]}],
    }
    north = answer("What about North?", db_path=db, context=context)
    context.update(north["metrics"])
    context["entities"] = [
        {"column": "region", "value": "South"},
        {"column": "region", "value": "North"},
    ]

    assert north["metrics"]["value"] == 100
    assert answer("How many transactions?", db_path=db, context=context)["metrics"]["matching_rows"] == 2
    comparison = answer("Compare both.", db_path=db, context=context)
    assert {row["group_value"] for row in comparison["table"]} == {"South", "North"}


def test_follow_up_filter_uses_previous_numeric_operation(tmp_path):
    db = tmp_path / "salary_followup.sqlite3"
    csv = tmp_path / "employees.csv"
    csv.write_text(
        "Employee,Department,Salary\n"
        "Asha,HR,80000\n"
        "Ravi,Sales,65000\n"
        "Mina,HR,90000\n",
        encoding="utf-8",
    )
    ingest_generic(csv, db)
    activate(db)

    first = answer("What is the average salary?", db_path=db)
    context = {"question": "What is the average salary?", **first["metrics"]}
    filtered = answer("Only HR.", db_path=db, context=context)

    assert filtered["metrics"]["value"] == 85000
    assert filtered["metrics"]["matching_rows"] == 2


def test_grouping_prefers_explicit_department_over_employee_column(tmp_path):
    db = tmp_path / "employee_grouping.sqlite3"
    csv = tmp_path / "employees.csv"
    csv.write_text(
        "Employee,Department,Salary\n"
        "Asha,HR,80000\n"
        "Ravi,Sales,65000\n"
        "Mina,HR,90000\n"
        "Dev,Sales,55000\n"
        "Dev,Sales,60000\n",
        encoding="utf-8",
    )

    ingest_generic(csv, db)
    activate(db)

    result = answer("Which department has more employees?", db_path=db)

    assert result["metrics"]["group_column"] == "department"
    assert result["table"][0]["group_value"] == "Sales"
