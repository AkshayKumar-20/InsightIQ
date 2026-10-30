from pathlib import Path
import json
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import Cookie, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .config import COOKIE_SECURE, DB_PATH, DATASET_PATH, FRONTEND_ORIGINS, SESSION_DAYS
from .database import initialize, connect
from .ingestion import latest_summary
from .schemas import AskRequest, AskResponse, HealthResponse
from .interpretation import interpret, SUPPORTED
from .services import execute
from .generic import answer as answer_generic, ingest_generic, latest as latest_generic, activate as activate_generic
from .ingestion import REQUIRED, ingest_csv
from . import analytics

app = FastAPI(title="InsightIQ API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
initialize()

SESSION_COOKIE = "insightiq_session"

def _password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _password_matches(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return secrets.compare_digest(password_hash, hashlib.sha256(password.encode("utf-8")).hexdigest())

def _session_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()

def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )

def _user_from_session(session_token: str | None):
    if not session_token:
        return None
    with connect() as connection:
        connection.execute("DELETE FROM auth_tokens WHERE expires_at IS NOT NULL AND expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
        return connection.execute(
            "SELECT users.id, users.name, users.email, users.role "
            "FROM users JOIN auth_tokens ON auth_tokens.user_id=users.id "
            "WHERE auth_tokens.token=? AND auth_tokens.expires_at > ?",
            (session_token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()

def _auth(payload: dict):
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if "@" not in email or len(password) < 6:
        raise HTTPException(422, "Enter a valid email and a password with at least 6 characters.")
    return email, password

@app.post("/api/auth/register")
def register(payload: dict):
    email, password = _auth(payload)
    name = str(payload.get("name") or email.split("@")[0]).strip()[:100]
    role = str(payload.get("role") or "").strip()[:100]
    if not role:
        raise HTTPException(422, "Employee role is required.")
    with connect() as connection:
        try:
            cursor = connection.execute("INSERT INTO users(email, name, role, password_hash) VALUES (?, ?, ?, ?)", (email, name, role, _password_hash(password)))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(409, "An account with this email already exists.")
            raise
    return {"user": {"id": cursor.lastrowid, "name": name, "email": email, "role": role}}

@app.post("/api/auth/login")
def login(payload: dict, response: Response):
    email, password = _auth(payload)
    with connect() as connection:
        user = connection.execute("SELECT id, name, email, role, password_hash FROM users WHERE email=?", (email,)).fetchone()
        if not user or not _password_matches(password, user["password_hash"]):
            raise HTTPException(401, "Incorrect email or password.")
        if len(user["password_hash"]) == 64:
            connection.execute("UPDATE users SET password_hash=? WHERE id=?", (_password_hash(password), user["id"]))
        token = secrets.token_urlsafe(32)
        connection.execute("INSERT INTO auth_tokens(token, user_id, expires_at) VALUES (?, ?, ?)", (token, user["id"], _session_expiry()))
    _set_session_cookie(response, token)
    return {"user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}}

@app.get("/api/auth/me")
def current_user(insightiq_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    user = _user_from_session(insightiq_session)
    if not user:
        raise HTTPException(401, "Your session has expired.")
    return dict(user)

@app.post("/api/auth/logout")
def logout(response: Response, insightiq_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    if insightiq_session:
        with connect() as connection:
            connection.execute("DELETE FROM auth_tokens WHERE token=?", (insightiq_session,))
    response.delete_cookie(SESSION_COOKIE)
    return {"success": True}

@app.on_event("startup")
def startup():
    initialize()

@app.get("/health", response_model=HealthResponse)
def health(): return {"status": "ok"}

@app.get("/api/health", response_model=HealthResponse)
def api_health(): return {"status": "ok"}

@app.get("/api/metadata")
def metadata():
    s = latest_summary()
    generic = latest_generic()
    with connect() as connection:
        active = connection.execute("SELECT value FROM app_state WHERE key='active_dataset'").fetchone()
    return {"dataset": s, "generic_dataset": generic, "active_dataset": active[0] if active else ("sales" if s.get("dataset_available") else None), "supported_questions": SUPPORTED, "generic_question_support": ["row_count", "columns", "numeric_aggregates", "year_filters", "month_filters", "name_filters"], "interpreter_mode": "fallback", "reporting_period": {"start": s.get("reporting_start"), "end": s.get("reporting_end")}}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...), conversation_id: int | None = None):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Upload a CSV file.")
    upload_dir = DATASET_PATH.parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / Path(file.filename).name
    target.write_bytes(await file.read())
    try:
        import pandas as pd
        columns = list(pd.read_csv(target, sep=None, engine="python", nrows=0).columns)
        if all(required in columns for required in REQUIRED):
            result = {"dataset_type": "sales", "ingestion": ingest_csv(target)}
            with connect() as connection:
                connection.execute("INSERT INTO app_state(key, value) VALUES('active_dataset', 'sales') ON CONFLICT(key) DO UPDATE SET value='sales'")
                if conversation_id:
                    connection.execute("UPDATE conversations SET dataset_ref='sales', context_json=NULL WHERE id=?", (conversation_id,))
            return result
        result = ingest_generic(target)
        active_dataset = activate_generic()
        result["dataset_id"] = f"generic:{active_dataset['id']}"
        result["profile"] = {
            "filename": active_dataset["filename"],
            "row_count": active_dataset["row_count"],
            "column_count": active_dataset["column_count"],
            "missing_values": active_dataset.get("missing_values", 0),
            "duplicate_rows": active_dataset.get("duplicate_rows", 0),
            "columns": active_dataset["columns"],
            "summary": active_dataset.get("summary", ""),
        }
        if conversation_id:
            with connect() as connection:
                connection.execute("UPDATE conversations SET dataset_ref=?, context_json=NULL WHERE id=?", (result["dataset_id"], conversation_id))
        return result
    except (ValueError, KeyError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(503, "The CSV could not be imported.")

@app.get("/api/analytics/summary")
def get_summary():
    try: return analytics.summary()
    except Exception: raise HTTPException(503, "Analytics database is unavailable.")

@app.get("/api/analytics/trends")
def get_trends():
    try: return {"data": analytics.trends()}
    except Exception: raise HTTPException(503, "Analytics database is unavailable.")

@app.get("/api/analytics/monthly")
def get_monthly():
    return get_trends()

@app.get("/api/analytics/products")
def get_products():
    try: return {"data": analytics.products()}
    except Exception: raise HTTPException(503, "Analytics database is unavailable.")

@app.get("/api/analytics/regions")
def get_regions():
    try: return {"data": analytics.regions()}
    except Exception: raise HTTPException(503, "Analytics database is unavailable.")

@app.get("/api/analytics/comparison")
def get_comparison(start_month: str = "2026-01", end_month: str = "2026-02"):
    try:
        return analytics.comparison(start_month, end_month)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.get("/api/data-quality")
def data_quality():
    try:
        with connect() as conn:
            latest = conn.execute("SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 1").fetchone()
            rejected = conn.execute("SELECT reason, COUNT(*) count FROM rejected_records GROUP BY reason ORDER BY count DESC").fetchall()
        return {"ingestion": dict(latest) if latest else {"dataset_available": False},
                "rejections": [dict(row) for row in rejected],
                "policy": analytics.POLICY}
    except Exception:
        raise HTTPException(503, "Data-quality information is unavailable.")

@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest):
    try:
        question = request.question.strip().lower()
        if question in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
            return {"success": True, "question": request.question, "intent": "greeting",
                    "answer": "Hello! 👋 I’m InsightIQ. Upload a CSV and ask me about its numbers, people, dates, products, or any matching records.",
                    "metrics": {}, "table": [], "chart": None,
                    "sql_explanation": "General conversation response; no database query was needed.",
                    "data_policy": "General assistant response.", "interpreter_mode": "conversation"}
        if any(phrase in question for phrase in ("what can you do", "how can you help", "help me", "what is your purpose")):
            return {"success": True, "question": request.question, "intent": "help",
                    "answer": "I can read your active CSV, answer numeric questions, filter by dates or employees, list matching rows, and explain business trends. 📊",
                    "metrics": {}, "table": [], "chart": None,
                    "sql_explanation": "General capability response; no database query was needed.",
                    "data_policy": "General assistant response.", "interpreter_mode": "conversation"}
        if any(phrase in question for phrase in ("thank you", "thanks", "who are you", "good job")):
            return {"success": True, "question": request.question, "intent": "conversation",
                    "answer": "You’re welcome! 😊 I’m here whenever you want to explore your data.",
                    "metrics": {}, "table": [], "chart": None,
                    "sql_explanation": "General conversation response; no database query was needed.",
                    "data_policy": "General assistant response.", "interpreter_mode": "conversation"}
        generic = latest_generic()
        with connect() as connection:
            has_sales = connection.execute("SELECT EXISTS(SELECT 1 FROM transactions LIMIT 1)").fetchone()[0]
            active = connection.execute("SELECT value FROM app_state WHERE key='active_dataset'").fetchone()
        active_value = active[0] if active else ("sales" if has_sales else "generic")
        context = {}
        conversation_dataset = None
        if request.conversation_id:
            with connect() as connection:
                row = connection.execute("SELECT context_json, dataset_ref FROM conversations WHERE id=?", (request.conversation_id,)).fetchone()
                if row:
                    conversation_dataset = row["dataset_ref"]
                    if row["context_json"]:
                        context = json.loads(row["context_json"])
        if conversation_dataset:
            with connect() as connection:
                connection.execute(
                    "INSERT INTO app_state(key, value) VALUES('active_dataset', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (conversation_dataset,),
                )
            active_value = conversation_dataset
            generic = latest_generic(
                dataset_id=conversation_dataset.split(":", 1)[1]
            ) if conversation_dataset.startswith("generic:") else generic
        if generic and active_value.startswith("generic:"):
            result = answer_generic(request.question, context=context, dataset_ref=active_value)
            result["dataset_id"] = active_value
            result["dataset_name"] = generic.get("filename")
            if request.conversation_id:
                metrics = result.get("metrics", {})
                entities = list(context.get("entities", []))
                selected_group = metrics.get("selected_group")
                group_column = metrics.get("group_column") or context.get("group_column")
                if selected_group and group_column:
                    entity = {"column": group_column, "value": selected_group}
                    if entity not in entities:
                        entities.append(entity)
                next_context = {
                    "question": request.question,
                    "dataset_ref": active_value,
                    "last_operation": result.get("intent") or ("grouped" if result.get("chart") else "query"),
                    **metrics,
                    "entities": entities[-10:],
                }
                with connect() as connection:
                    connection.execute("UPDATE conversations SET context_json=? WHERE id=?", (json.dumps(next_context), request.conversation_id))
            return {"success": True, "question": request.question, "intent": "generic_csv", **result, "data_policy": "Answer generated from the active uploaded CSV using safe read-only operations.", "interpreter_mode": "data analysis"}
        interpretation, mode = interpret(request.question)
        result = execute(interpretation)
        return {"success": True, "question": request.question, "intent": interpretation.intent,
                **result, "data_policy": analytics.POLICY, "interpreter_mode": mode}
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(503, "The analytics database is unavailable.")

@app.get("/api/profile")
def get_profile():
    with connect() as connection:
        connection.execute("INSERT OR IGNORE INTO profiles(id) VALUES(1)")
        return dict(connection.execute("SELECT id, name, email, role, updated_at FROM profiles WHERE id=1").fetchone())

@app.put("/api/profile")
def update_profile(payload: dict):
    name = str(payload.get("name") or "").strip()[:100]
    email = str(payload.get("email") or "").strip()[:200]
    role = str(payload.get("role") or "Analyst").strip()[:100]
    if not name:
        raise HTTPException(422, "Profile name is required.")
    with connect() as connection:
        connection.execute("INSERT INTO profiles(id, name, email, role) VALUES(1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, email=excluded.email, role=excluded.role, updated_at=CURRENT_TIMESTAMP", (name, email, role))
        return dict(connection.execute("SELECT id, name, email, role, updated_at FROM profiles WHERE id=1").fetchone())

@app.post("/api/chat", response_model=AskResponse)
def chat(request: AskRequest):
    return ask(request)

@app.get("/api/conversations")
def list_conversations():
    with connect() as conn:
        rows = conn.execute("SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC, id DESC").fetchall()
    return {"data": [dict(row) for row in rows]}

@app.post("/api/conversations")
def create_conversation(payload: dict | None = None):
    title = str((payload or {}).get("title") or "New conversation").strip()[:120] or "New conversation"
    with connect() as conn:
        active = conn.execute("SELECT value FROM app_state WHERE key='active_dataset'").fetchone()
        dataset_ref = active["value"] if active else None
        cursor = conn.execute(
            "INSERT INTO conversations(title, dataset_ref) VALUES (?, ?)",
            (title, dataset_ref),
        )
        conversation_id = cursor.lastrowid
    return {"id": conversation_id, "title": title, "dataset_ref": dataset_ref, "messages": []}

@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: int):
    with connect() as conn:
        conversation = conn.execute("SELECT id, title, dataset_ref, created_at, updated_at FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        messages = conn.execute("SELECT id, role, content, result_json, created_at FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,)).fetchall()
    if not conversation:
        raise HTTPException(404, "Conversation not found.")
    result = []
    for row in messages:
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json")) if item["result_json"] else None
        result.append(item)
    return {**dict(conversation), "messages": result}

@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int):
    with connect() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    if cursor.rowcount == 0:
        raise HTTPException(404, "Conversation not found.")
    return {"deleted": True}

@app.patch("/api/conversations/{conversation_id}")
def rename_conversation(conversation_id: int, payload: dict):
    title = str(payload.get("title") or "").strip()[:120]
    if not title:
        raise HTTPException(422, "Conversation title is required.")
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE conversations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (title, conversation_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(404, "Conversation not found.")
    return {"id": conversation_id, "title": title}

@app.post("/api/conversations/{conversation_id}/messages")
def add_message(conversation_id: int, payload: dict):
    role = payload.get("role")
    content = str(payload.get("content") or "").strip()
    if role not in {"user", "assistant"} or not content:
        raise HTTPException(422, "A valid role and non-empty content are required.")
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
            raise HTTPException(404, "Conversation not found.")
        conn.execute("INSERT INTO messages(conversation_id, role, content, result_json) VALUES (?, ?, ?, ?)",
                     (conversation_id, role, content, json.dumps(payload.get("result")) if payload.get("result") is not None else None))
        conn.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversation_id,))
    return {"saved": True}
