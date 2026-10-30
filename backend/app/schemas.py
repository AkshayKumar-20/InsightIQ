from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict

Intent = Literal["total_revenue", "top_product", "monthly_trend", "top_region", "revenue_comparison"]

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    conversation_id: int | None = None

class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    parameters: dict[str, str] = Field(default_factory=dict)

class AskResponse(BaseModel):
    success: bool
    question: str
    intent: str | None = None
    answer: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    table: list[dict[str, Any]] = Field(default_factory=list)
    chart: dict[str, Any] | None = None
    sql_explanation: str = ""
    data_policy: str
    interpreter_mode: str

class HealthResponse(BaseModel):
    status: str
