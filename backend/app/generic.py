import json
import re
import uuid
from pathlib import Path

import pandas as pd

from .database import connect, initialize


STOPWORDS = {
    "what", "which", "where", "when", "show", "list", "give", "find", "tell",
    "me", "about", "the", "this", "that", "from", "with", "for", "and", "can",
    "you", "please", "data", "csv", "file", "records", "record", "rows", "row",
    "of", "is", "are", "was", "were", "has", "have", "does", "do", "all",
}
NUMERIC_ALIASES = {
    "amount": ("amount", "revenue", "sales", "price", "value", "total"),
    "cost": ("cost", "price", "amount", "value"),
    "salary": ("salary", "pay", "wage", "compensation"),
    "revenue": ("revenue", "sales", "amount", "income", "value"),
    "sales": ("sales", "revenue", "amount", "value"),
    "quantity": ("quantity", "qty", "units", "count", "stock"),
}


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _normalise(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "na", "n/a"} else text


def _column_type(series: pd.Series) -> str:
    cleaned = series.map(_normalise)
    non_empty = cleaned[cleaned.ne("")]
    if non_empty.empty:
        return "text"
    numeric = pd.to_numeric(non_empty.str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce")
    if numeric.notna().mean() >= 0.8:
        return "number"
    dates = pd.to_datetime(non_empty, errors="coerce", format="mixed", dayfirst=False)
    if dates.notna().mean() >= 0.8:
        return "date"
    unique = cleaned.nunique(dropna=True)
    return "categorical" if unique <= max(20, len(cleaned) * 0.1) else "text"


def ingest_generic(source: Path | str, db_path=None) -> dict:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Dataset not found: {source}")
    if b"\x00" in source.read_bytes():
        raise ValueError("CSV file contains invalid binary data.")
    try:
        frame = pd.read_csv(
            source,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            on_bad_lines="error",
        )
    except UnicodeDecodeError:
        frame = pd.read_csv(
            source,
            sep=None,
            engine="python",
            encoding="latin-1",
            on_bad_lines="error",
        )
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV file is empty.") from exc
    except pd.errors.ParserError as exc:
        raise ValueError("CSV file is malformed and could not be parsed.") from exc
    if frame.empty and len(frame.columns) == 0:
        raise ValueError("CSV must contain a header row.")
    if len(frame.columns) == 0 or any(not str(column).strip() for column in frame.columns):
        raise ValueError("CSV must contain named columns.")
    columns = []
    seen = set()
    for raw in frame.columns:
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", str(raw).strip()).strip("_").lower() or "column"
        name, suffix = base, 2
        while name in seen:
            name = f"{base}_{suffix}"
            suffix += 1
        seen.add(name)
        values = frame[raw].map(_normalise)
        columns.append({
            "name": name,
            "label": str(raw).strip(),
            "type": _column_type(frame[raw]),
            "missing": int(values.eq("").sum()),
            "sample_values": values[values.ne("")].head(5).tolist(),
        })
    frame.columns = [column["name"] for column in columns]
    table_name = f"dataset_{uuid.uuid4().hex}"
    initialize(db_path)
    definitions = ", ".join(f"{_quote(column['name'])} TEXT" for column in columns)
    with connect(db_path) as connection:
        connection.execute(f"CREATE TABLE {_quote(table_name)} ({definitions})")
        values = [[_normalise(value) or None for value in row] for row in frame.itertuples(index=False, name=None)]
        if values:
            placeholders = ",".join("?" for _ in columns)
            connection.executemany(f"INSERT INTO {_quote(table_name)} VALUES ({placeholders})", values)
        profile = {
            "filename": source.name,
            "row_count": len(frame),
            "column_count": len(columns),
            "columns": columns,
            "duplicate_rows": int(frame.duplicated().sum()),
            "missing_values": int(sum(column["missing"] for column in columns)),
            "summary": (
                f"{source.name} contains {len(frame):,} rows and {len(columns):,} columns. "
                f"It has {sum(column['missing'] for column in columns):,} missing values "
                f"and {int(frame.duplicated().sum()):,} duplicate rows."
            ),
        }
        connection.execute(
            "INSERT INTO generic_datasets(source, table_name, columns_json, row_count) VALUES (?, ?, ?, ?)",
            (str(source), table_name, json.dumps(profile), len(frame)),
        )
    return {
        "dataset_type": "generic",
        "dataset_id": None,
        "table_name": table_name,
        "columns": columns,
        "row_count": len(frame),
        "column_count": len(columns),
        "missing_values": int(sum(column["missing"] for column in columns)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "summary": profile["summary"],
        "filename": source.name,
    }


def latest(db_path=None, dataset_id=None):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM generic_datasets WHERE id=? LIMIT 1" if dataset_id else "SELECT * FROM generic_datasets ORDER BY id DESC LIMIT 1",
            (dataset_id,) if dataset_id else (),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    raw_profile = json.loads(result.pop("columns_json"))
    if isinstance(raw_profile, dict):
        result.update(raw_profile)
        result["columns"] = raw_profile.get("columns", [])
    else:
        result["columns"] = raw_profile
    return result


def activate(db_path=None):
    dataset = latest(db_path)
    if not dataset:
        raise ValueError("No generic CSV has been uploaded.")
    with connect(db_path) as connection:
        connection.execute(
            "INSERT INTO app_state(key, value) VALUES('active_dataset', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (f"generic:{dataset['id']}",),
        )
    return dataset


def _dataset(db_path=None, dataset_ref=None):
    dataset_id = None
    if dataset_ref and str(dataset_ref).startswith("generic:"):
        dataset_id = str(dataset_ref).split(":", 1)[1]
    dataset = latest(db_path, dataset_id)
    if not dataset:
        raise ValueError("No generic CSV has been uploaded.")
    return dataset


def _tokens(text):
    return [token for token in re.findall(r"[a-z0-9][a-z0-9._'-]{1,}", text.lower()) if token not in STOPWORDS]


def _find_column(columns, text, types=None):
    candidates = [column for column in columns if not types or column["type"] in types]
    normal = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    exact_matches = []
    for column in candidates:
        name = column["name"].replace("_", " ")
        label = column["label"].lower()
        for value in (name, label):
            if re.search(rf"\b{re.escape(value)}(?:s)?\b", normal):
                exact_matches.append((len(value), column))
                break
    if exact_matches:
        return max(exact_matches, key=lambda match: match[0])[1]
    for alias, names in NUMERIC_ALIASES.items():
        if alias in normal:
            for name in names:
                match = next((column for column in candidates if name in column["name"].lower() or name in column["label"].lower()), None)
                if match:
                    return match
    return candidates[0] if len(candidates) == 1 else None


def _filters(text, columns):
    conditions, params, labels = [], [], []
    date_columns = [column for column in columns if column["type"] == "date" or any(x in column["name"] for x in ("date", "year", "month", "time"))]
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    if years and date_columns:
        conditions.append("(" + " OR ".join(f"substr(CAST({_quote(c['name'])} AS TEXT),1,4)=?" for c in date_columns) + ")")
        params.extend([years[0]] * len(date_columns))
        labels.append(f"year {years[0]}")
    months = re.findall(r"\b(19\d{2})[-/](0?[1-9]|1[0-2])\b", text)
    if months and date_columns:
        month = f"{months[0][0]}-{int(months[0][1]):02d}"
        conditions.append("(" + " OR ".join(f"substr(CAST({_quote(c['name'])} AS TEXT),1,7)=?" for c in date_columns) + ")")
        params.extend([month] * len(date_columns))
        labels.append(f"month {month}")
    text_columns = [column for column in columns if column["type"] in {"text", "categorical"}]
    explicit = re.search(r"\b(?:employee|staff|person|user|name|region|department|manufacturer|product|category)\s+(?:named\s+)?([a-z][a-z0-9 .&'_-]{1,60}?)(?=\s+(?:in|for|during|on|from|with)\b|[?.!,]|$)", text, re.I)
    if explicit and text_columns:
        value = explicit.group(1).strip()
        if value.lower().split(" ", 1)[0] in {"has", "is", "with", "highest", "lowest", "most", "least"}:
            explicit = None
    if explicit and text_columns:
        value = explicit.group(1).strip()
        column = _find_column(text_columns, text)
        if column:
            conditions.append(f"LOWER(CAST({_quote(column['name'])} AS TEXT)) LIKE ?")
            params.append(f"%{value.lower()}%")
            labels.append(f"{column['label']} contains {value}")
    if not explicit and re.match(r"^\s*(?:show|list|find|tell me about)\b", text, re.I):
        tokens = _tokens(text)
        known_values = {
            str(sample).lower()
            for column in text_columns
            for sample in column.get("sample_values", [])
        }
        values = [token for token in tokens if token in known_values]
        if values:
            conditions.append("(" + " OR ".join(
                f"LOWER(CAST({_quote(column['name'])} AS TEXT)) LIKE ?"
                for column in text_columns
            ) + ")")
            params.extend(f"%{values[0]}%" for _ in text_columns)
            labels.append(f"value contains {values[0]}")
    return conditions, params, labels


def _limit_from_question(text: str, default: int = 10) -> int:
    match = re.search(r"\b(?:top|first|last|bottom)\s+(\d{1,3}|one|two|three|four|five|ten|twenty)\b", text)
    if not match:
        return default
    values = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20}
    return max(1, min(int(match.group(1)) if match.group(1).isdigit() else values[match.group(1)], 100))


def _date_columns(columns):
    return [column for column in columns if column["type"] == "date" or any(
        token in column["name"] for token in ("date", "year", "month", "time")
    )]


def _column_by_ref(columns, reference):
    if not reference:
        return None
    value = str(reference).lower()
    return next(
        (column for column in columns if column["name"].lower() == value or column["label"].lower() == value),
        None,
    )


def _context_value_filter(text, columns, context):
    if not context or not re.search(r"\b(?:only|just|same|that|it|them)\b", text):
        return None
    candidates = [column for column in columns if column["type"] in {"text", "categorical"}]
    preferred = _column_by_ref(columns, context.get("group_column"))
    if preferred:
        candidates = [preferred]
    words = {token.strip(".,!?;:") for token in _tokens(text)}
    for column in candidates:
        for sample in column.get("sample_values", []):
            value = str(sample).strip()
            if value and value.lower() in words:
                return column, value
    return None


def answer(question: str, db_path=None, context: dict | None = None, dataset_ref: str | None = None) -> dict:
    dataset = _dataset(db_path, dataset_ref)
    text = question.lower().strip()
    columns = dataset["columns"]
    table = _quote(dataset["table_name"])
    conditions, params, labels = _filters(text, columns)
    contextual_filter = _context_value_filter(text, columns, context)
    if contextual_filter and not conditions:
        filter_column, filter_value = contextual_filter
        conditions.append(f"LOWER(CAST({_quote(filter_column['name'])} AS TEXT)) LIKE ?")
        params.append(f"%{filter_value.lower()}%")
        labels.append(f"{filter_column['label']} contains {filter_value}")
    follow_up = re.search(r"\b(?:what about|how about|show|tell me about)\s+([a-z][a-z0-9 .&'_-]{1,60})[?.!]*$", text, re.I)
    if follow_up and context and context.get("group_column") and context.get("column"):
        value = follow_up.group(1).strip().rstrip("?.!")
        group_column = next((column for column in columns if column["name"].lower() == str(context["group_column"]).lower()), None)
        requested_column = str(context["column"]).lower()
        numeric = next((column for column in columns if column["label"].lower() == requested_column or column["name"].lower() == requested_column), None)
        if value and not re.fullmatch(r"(19\d{2}|20\d{2})", value) and group_column and numeric:
            where = f" WHERE LOWER(CAST({_quote(group_column['name'])} AS TEXT)) LIKE ?"
            with connect(db_path) as connection:
                row = connection.execute(
                    f"SELECT SUM(CAST({_quote(numeric['name'])} AS REAL)) AS value, COUNT(*) AS records FROM {_quote(dataset['table_name'])}{where}",
                    (f"%{value.lower()}%",),
                ).fetchone()
            total = float(row["value"] or 0)
            return {
                "answer": f"{value} has {total:,.2f} {numeric['label']} across {row['records']:,} records.",
                "metrics": {"group": group_column["label"], "selected_group": value, "column": numeric["label"], "value": round(total, 2), "records": row["records"]},
                "table": [{"group_value": value, "value": round(total, 2), "records": row["records"]}],
                "chart": None,
                "sql_explanation": "Applied the previous grouped metric to the requested categorical value.",
            }
    if context and re.fullmatch(r"(19\d{2}|20\d{2})", text) and context.get("question"):
        return answer(f"{context['question']} {text}", db_path=db_path, context=None, dataset_ref=dataset_ref)
    if context and context.get("group_column") and context.get("selected_group") and (
        not conditions or bool(re.search(r"\b(count|how many|number of|total rows?)\b", text))
    ) and not follow_up:
        group_column = next((column for column in columns if column["name"] == context["group_column"]), None)
        if group_column:
            conditions.append(f"LOWER(CAST({_quote(group_column['name'])} AS TEXT)) LIKE ?")
            params.append(f"%{str(context['selected_group']).lower()}%")
            labels.append(f"{group_column['label']} contains {context['selected_group']}")
    if context and re.fullmatch(r"(19\d{2}|20\d{2})", text):
        date_columns = [column for column in columns if column["type"] == "date" or "date" in column["name"]]
        if date_columns:
            conditions.append("(" + " OR ".join(f"substr(CAST({_quote(c['name'])} AS TEXT),1,4)=?" for c in date_columns) + ")")
            params.extend([text] * len(date_columns))
            labels.append(f"year {text}")
    if follow_up and context:
        value = follow_up.group(1).strip().rstrip("?.!")
        if re.fullmatch(r"(19\d{2}|20\d{2})", value):
            value = ""
        text_columns = [column for column in columns if column["type"] in {"text", "categorical"}]
        matching_column = next((column for column in text_columns if context.get("group_column") == column["name"]), None)
        if not matching_column:
            matching_column = _find_column(text_columns, context.get("question", ""))
        if matching_column:
            conditions.append(f"LOWER(CAST({_quote(matching_column['name'])} AS TEXT)) LIKE ?")
            params.append(f"%{value.lower()}%")
            labels.append(f"{matching_column['label']} contains {value}")
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    note = f" Filters: {', '.join(labels)}." if labels else ""
    with connect(db_path) as connection:
        matching = connection.execute(f"SELECT COUNT(*) FROM {table}{where}", params).fetchone()[0]

    if context and len(context.get("entities", [])) >= 2 and re.search(r"\b(compare|both|versus|vs|difference)\b", text):
        compare_column = _column_by_ref(columns, context.get("column")) or _find_column(columns, context.get("question", ""), {"number"})
        group_column = _column_by_ref(columns, context.get("group_column"))
        if compare_column and group_column:
            rows = []
            with connect(db_path) as connection:
                for entity in context["entities"][-2:]:
                    row = connection.execute(
                        f"SELECT SUM(CAST({_quote(compare_column['name'])} AS REAL)) AS value, COUNT(*) AS records "
                        f"FROM {table} WHERE LOWER(CAST({_quote(group_column['name'])} AS TEXT)) LIKE ?",
                        (f"%{str(entity['value']).lower()}%",),
                    ).fetchone()
                    rows.append({"group_value": entity["value"], "value": round(float(row["value"] or 0), 2), "records": row["records"]})
            return {
                "answer": f"Compared {compare_column['label']} for {rows[0]['group_value']} and {rows[1]['group_value']}.",
                "metrics": {"group": group_column["label"], "group_column": group_column["name"], "column": compare_column["label"], "entities": [row["group_value"] for row in rows]},
                "table": rows,
                "chart": {"type": "bar", "x_key": "group_value", "y_key": "value", "data": rows},
                "sql_explanation": "Compared the previous conversation entities using validated columns and parameterized filters.",
            }

    if follow_up and context and context.get("column") and value:
        matching_column = next(
            (column for column in columns if column["name"] == context.get("group_column")),
            matching_column if "matching_column" in locals() else None,
        )
        requested_column = str(context["column"]).lower()
        numeric = next((column for column in columns if column["label"].lower() == requested_column or column["name"].lower() == requested_column), None)
        if numeric and matching_column:
            with connect(db_path) as connection:
                row = connection.execute(
                    f"SELECT SUM(CAST({_quote(numeric['name'])} AS REAL)) AS value, COUNT(*) AS records FROM {table}{where}",
                    params,
                ).fetchone()
            total = float(row["value"] or 0)
            return {
                "answer": f"{value} has {total:,.2f} {numeric['label']} across {row['records']:,} records.{note}",
                "metrics": {"group": matching_column["label"], "selected_group": value, "column": numeric["label"], "value": round(total, 2), "records": row["records"]},
                "table": [{"group_value": value, "value": round(total, 2), "records": row["records"]}],
                "chart": None,
                "sql_explanation": "Applied the previous grouped metric to the requested categorical value.",
            }

    if re.search(r"\b(profile|overview|available|describe|schema|columns?|fields?|headers?)\b", text):
        rows = [{"column": c["label"], "normalized_name": c["name"], "type": c["type"], "missing": c.get("missing", 0), "samples": ", ".join(c.get("sample_values", []))} for c in columns]
        return {"answer": f"{dataset.get('filename', 'This CSV')} has {dataset['row_count']:,} rows and {len(columns)} columns.", "metrics": {"rows": dataset["row_count"], "columns": len(columns), "duplicate_rows": dataset.get("duplicate_rows", 0)}, "table": rows, "chart": None, "sql_explanation": "Returned the stored dataset profile."}

    if re.search(r"\b(missing|null|empty|incomplete)\b", text):
        rows = [{"column": c["label"], "missing": c.get("missing", 0)} for c in columns if c.get("missing", 0)]
        return {"answer": f"{sum(row['missing'] for row in rows):,} missing values were found across {len(rows)} columns.", "metrics": {"columns_with_missing": len(rows)}, "table": rows, "chart": None, "sql_explanation": "Used the ingestion profile's missing-value counts."}

    if re.search(r"\b(duplicate|duplicates)\b", text):
        return {"answer": f"{dataset.get('duplicate_rows', 0):,} duplicate rows were found.", "metrics": {"duplicate_rows": dataset.get("duplicate_rows", 0)}, "table": [], "chart": None, "sql_explanation": "Compared complete rows during CSV profiling."}

    if re.search(r"\b(first|sample|examples?|show|list|display|records?|names?)\b", text) and not re.search(r"\b(highest|lowest|sum|total|average|mean|minimum|maximum|top|bottom|group|grouped| by |count|how many|number of)\b", text):
        limit = _limit_from_question(text)
        selected_columns = columns
        if re.search(r"\b(names?|employees?|people|products?)\b", text):
            text_columns = [column for column in columns if column["type"] in {"text", "categorical"}]
            selected = _find_column(text_columns, text)
            if selected:
                selected_columns = [selected]
        projection = ", ".join(_quote(column["name"]) for column in selected_columns)
        with connect(db_path) as connection:
            rows = [dict(row) for row in connection.execute(f"SELECT {projection} FROM {table}{where} LIMIT ?", (*params, limit)).fetchall()]
        return {"answer": f"Here are {len(rows):,} matching rows from {dataset.get('filename', 'the CSV')}.{note}", "metrics": {"matching_rows": matching, "rows_returned": len(rows)}, "table": rows, "chart": None, "sql_explanation": "Returned validated rows with parameterized filters and a 100-row limit."}

    numeric = _find_column(columns, text, {"number"})
    group = _find_column(columns, text, {"categorical", "text"})
    rank = re.search(r"\b(highest|top|maximum|max|lowest|bottom|minimum|min|most|more|fewest|least)\b", text)
    top_n = _limit_from_question(text, 1)
    if group and re.search(r"\b(group|grouped|by|each|per)\b", text) and not rank:
        query = f"SELECT {_quote(group['name'])} AS group_value, COUNT(*) AS records FROM {table}{where} GROUP BY {_quote(group['name'])} ORDER BY records DESC, group_value LIMIT 100"
        with connect(db_path) as connection:
            rows = [dict(row) for row in connection.execute(query, params).fetchall()]
        return {"answer": f"Grouped {matching:,} records by {group['label']}.{note}", "metrics": {"group": group["label"], "groups": len(rows)}, "table": rows, "chart": {"type": "bar", "x_key": "group_value", "y_key": "records", "data": rows}, "sql_explanation": "Grouped a validated categorical column and counted records safely."}
    if rank and group and re.search(r"\b(employee|employees|records|rows|people|count|number)\b", text):
        numeric = None
    if rank and group and not numeric:
        direction = "DESC" if rank.group(1) in {"highest", "top", "maximum", "max", "most", "more"} else "ASC"
        query = f"SELECT {_quote(group['name'])} AS group_value, COUNT(*) AS records FROM {table}{where} GROUP BY {_quote(group['name'])} ORDER BY records {direction}, group_value LIMIT ?"
        with connect(db_path) as connection:
            rows = [dict(row) for row in connection.execute(query, (*params, top_n)).fetchall()]
        if rows:
            return {"answer": f"{rows[0]['group_value']} has the {rank.group(1)} number of records ({rows[0]['records']:,}).{note}", "metrics": {"group": group["label"], "group_column": group["name"], "records": rows[0]["records"]}, "table": rows, "chart": {"type": "bar", "x_key": "group_value", "y_key": "records", "data": rows}, "sql_explanation": "Grouped a validated categorical column and ranked groups by record count."}
    if re.search(r"\btop\b", text) and not group and numeric:
        limit = _limit_from_question(text, 5)
        query = f"SELECT * FROM {table}{where} ORDER BY CAST({_quote(numeric['name'])} AS REAL) DESC LIMIT ?"
        with connect(db_path) as connection:
            rows = [dict(row) for row in connection.execute(query, (*params, limit)).fetchall()]
        return {"answer": f"Here are the top {len(rows)} records by {numeric['label']}.{note}", "metrics": {"column": numeric["label"], "rows_returned": len(rows)}, "table": rows, "chart": None, "sql_explanation": "Ordered a validated numeric column descending with a bounded top-N limit."}
    if rank and numeric and group:
        direction = "DESC" if rank.group(1) in {"highest", "top", "maximum", "max", "most", "more"} else "ASC"
        query = f"SELECT {_quote(group['name'])} AS group_value, ROUND(SUM(CAST({_quote(numeric['name'])} AS REAL)),2) AS value, COUNT(*) AS records FROM {table}{where} GROUP BY {_quote(group['name'])} ORDER BY value {direction}, group_value LIMIT ?"
        with connect(db_path) as connection:
            rows = [dict(row) for row in connection.execute(query, (*params, top_n)).fetchall()]
        if rows:
            return {"answer": f"{rows[0]['group_value']} has the {rank.group(1)} {numeric['label']} at {rows[0]['value']:,.2f}.{note}", "metrics": {"group": group["label"], "group_column": group["name"], "selected_group": rows[0]["group_value"], "column": numeric["label"], "value": rows[0]["value"]}, "table": rows, "chart": {"type": "bar", "x_key": "group_value", "y_key": "value", "data": rows}, "sql_explanation": "Grouped and ranked validated columns using parameterized filters."}

    if rank and numeric and not group:
        aggregate = "MAX" if rank.group(1) in {"highest", "top", "maximum", "max", "most", "more"} else "MIN"
        with connect(db_path) as connection:
            value = connection.execute(
            f"SELECT {aggregate}(CAST({_quote(numeric['name'])} AS REAL)) FROM {table}{where}",
            params,
            ).fetchone()[0]
        result_value = float(value or 0)
        return {
            "answer": f"The {rank.group(1)} {numeric['label']} is {result_value:,.2f}.{note}",
            "metrics": {"column": numeric["label"], "value": round(result_value, 2), "matching_rows": matching},
            "table": [],
            "chart": None,
            "sql_explanation": f"Applied the approved {aggregate} aggregate to the validated numeric column.",
        }

    if re.search(r"\b(unique|distinct)\b", text):
        column = _find_column(columns, text)
        if column:
            with connect(db_path) as connection:
                value = connection.execute(f"SELECT COUNT(DISTINCT {_quote(column['name'])}) FROM {table}{where}", params).fetchone()[0]
            return {"answer": f"There are {value:,} unique {column['label']} values.{note}", "metrics": {"column": column["label"], "unique_values": value}, "table": [], "chart": None, "sql_explanation": "Counted distinct values from a validated column."}

    if re.search(r"\b(count|how many|number of|total rows?)\b", text) or text in {"count", "total", "records"}:
        return {"answer": f"There are {matching:,} matching records.{note}", "metrics": {"matching_rows": matching}, "table": [], "chart": None, "sql_explanation": "Counted rows using parameterized filters."}

    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    if len(years) >= 2 and re.search(r"\b(compare|comparison|versus|vs|difference|change)\b", text):
        dates = _date_columns(columns)
        if not dates:
            raise ValueError("This dataset has no date column to compare.")
        compare_column = numeric or _find_column(columns, text, {"number"})
        if not compare_column:
            raise ValueError("Tell me which numeric column to compare.")
        values = []
        with connect(db_path) as connection:
            for year in years[:2]:
                year_where = "(" + " OR ".join(
                    f"substr(CAST({_quote(date['name'])} AS TEXT),1,4)=?" for date in dates
                ) + ")"
                values.append(connection.execute(
                    f"SELECT SUM(CAST({_quote(compare_column['name'])} AS REAL)) FROM {table} WHERE {year_where}",
                    [year] * len(dates),
                ).fetchone()[0] or 0)
        change = float(values[1]) - float(values[0])
        rows = [{"year": years[0], "value": round(float(values[0]), 2)}, {"year": years[1], "value": round(float(values[1]), 2)}]
        return {"answer": f"{compare_column['label']} was {float(values[0]):,.2f} in {years[0]} and {float(values[1]):,.2f} in {years[1]}; change: {change:,.2f}.", "metrics": {"column": compare_column["label"], years[0]: round(float(values[0]), 2), years[1]: round(float(values[1]), 2), "change": round(change, 2)}, "table": rows, "chart": {"type": "bar", "x_key": "year", "y_key": "value", "data": rows}, "sql_explanation": "Compared parameterized year filters on validated date and numeric columns."}

    if years and re.search(r"\b(what happened|during|in|for)\b", text) and _date_columns(columns):
        metrics = {"matching_rows": matching, "year": years[0]}
        parts = [f"{matching:,} records"]
        with connect(db_path) as connection:
            for column in [item for item in columns if item["type"] == "number"][:3]:
                value = connection.execute(
                    f"SELECT SUM(CAST({_quote(column['name'])} AS REAL)) FROM {table}{where}",
                    params,
                ).fetchone()[0]
                if value is not None:
                    metrics[column["label"]] = round(float(value), 2)
                    parts.append(f"total {column['label']} {float(value):,.2f}")
        return {"answer": f"In {years[0]}, the dataset contains " + ", ".join(parts) + ".", "metrics": metrics, "table": [], "chart": None, "sql_explanation": "Applied the detected year filter and summarized validated numeric columns."}

    operation = re.search(r"\b(sum|total|average|avg|mean|median|minimum|min|max|maximum)\b", text)
    if not operation and contextual_filter and context:
        operation = re.search(
            r"\b(sum|total|average|avg|mean|median|minimum|min|max|maximum)\b",
            str(context.get("question", "")),
        )
    if operation:
        column = _find_column(columns, text, {"number"}) or _column_by_ref(columns, context.get("column") if context else None)
        if not column:
            raise ValueError("I found numeric data, but need the numeric column you want to calculate.")
        aggregate = {"sum": "SUM", "total": "SUM", "average": "AVG", "avg": "AVG", "mean": "AVG", "median": "AVG", "minimum": "MIN", "min": "MIN", "maximum": "MAX", "max": "MAX"}[operation.group(1)]
        with connect(db_path) as connection:
            value = connection.execute(f"SELECT {aggregate}(CAST({_quote(column['name'])} AS REAL)) FROM {table}{where}", params).fetchone()[0]
        return {"answer": f"The {operation.group(1)} {column['label']} is {float(value or 0):,.2f}.{note}", "metrics": {"column": column["label"], "value": round(float(value or 0), 2), "matching_rows": matching}, "table": [], "chart": None, "sql_explanation": f"Applied the approved {aggregate} aggregate to a validated numeric column."}

    tokens = _tokens(text)
    text_columns = [column for column in columns if column["type"] in {"text", "categorical"}]
    if tokens and text_columns:
        search_conditions = ["(" + " OR ".join(f"LOWER(CAST({_quote(c['name'])} AS TEXT)) LIKE ?" for c in text_columns) + ")" for _ in tokens[:5]]
        search_params = [f"%{token}%" for token in tokens[:5] for _ in text_columns]
        with connect(db_path) as connection:
            rows = [dict(row) for row in connection.execute(f"SELECT * FROM {table} WHERE {' AND '.join(search_conditions)} LIMIT 100", search_params).fetchall()]
        if rows:
            return {"answer": f"I found {len(rows):,} matching rows in {dataset.get('filename', 'the CSV')}. 🔎", "metrics": {"matching_rows": len(rows)}, "table": rows, "chart": None, "sql_explanation": "Searched validated text columns using parameterized terms."}

    raise ValueError("I could not map that question to this CSV. Ask for total revenue or another numeric calculation, a count, profile, sample rows, a ranking, missing values, or a filter using a value from the file.")
