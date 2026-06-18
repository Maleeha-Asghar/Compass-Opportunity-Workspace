from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    user_id: str | None
    search_job_id: str | None
    user_query: str
    intent: str | None
    today: str

    profile: dict[str, Any]
    cv_text: str | None

    search_queries: list[str]
    raw_search_results: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    search_started_at: float

    deduplicated_opportunities: list[dict[str, Any]]
    prioritized_opportunities: list[dict[str, Any]]

    selected_opportunity: dict[str, Any] | None
    deadline_plan: list[dict[str, Any]] | None

    document_type: str | None
    generated_document: str | None
    grounding_flags: list[str]

    tracker_action: dict[str, Any] | None
    final_answer: str
    errors: list[str]
