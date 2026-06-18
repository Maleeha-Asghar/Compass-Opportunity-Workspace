from datetime import date
from typing import Any

from langgraph.graph import END, StateGraph

from app.state import AgentState


def build_langgraph(compass_graph: Any):
    workflow = StateGraph(AgentState)

    def route_intent(state: AgentState) -> AgentState:
        decision = compass_graph.intent_router.route(state.get("user_query", ""))
        return {**state, "intent": decision.intent}

    def route_by_intent(state: AgentState) -> str:
        return state.get("intent") or "find_opportunities"

    def profile_update(state: AgentState) -> AgentState:
        state = {**state}
        state.setdefault("today", date.today().isoformat())
        return compass_graph._profile_update(state)

    def find_opportunities(state: AgentState) -> AgentState:
        state = {**state}
        state.setdefault("today", date.today().isoformat())
        return compass_graph._find_opportunities(state)

    def draft_document(state: AgentState) -> AgentState:
        state = {**state}
        user_id = state.get("user_id")
        opportunity = state.get("selected_opportunity")
        if not user_id or not opportunity or not opportunity.get("id"):
            state.setdefault("errors", []).append("draft_document requires user_id and selected_opportunity.id.")
            return state
        document = compass_graph.draft_document(
            user_id=user_id,
            profile=state.get("profile", {}),
            opportunity_id=opportunity["id"],
            document_type=state.get("document_type") or "sop",
            cv_text=state.get("cv_text"),
        )
        state["generated_document"] = document.get("content")
        state["grounding_flags"] = document.get("grounding_flags", [])
        state["final_answer"] = "Generated a grounded document draft."
        return state

    def track_application(state: AgentState) -> AgentState:
        state = {**state}
        user_id = state.get("user_id")
        if not user_id:
            state.setdefault("errors", []).append("track_application requires user_id.")
            return state
        opportunity = state.get("selected_opportunity") or {}
        tracker_action = compass_graph.update_tracker(
            user_id=user_id,
            text=state.get("user_query", ""),
            opportunity_id=opportunity.get("id"),
        )
        state["tracker_action"] = tracker_action
        state["final_answer"] = "Updated the application tracker."
        return state

    def deadline_plan(state: AgentState) -> AgentState:
        state = {**state}
        user_id = state.get("user_id")
        opportunity = state.get("selected_opportunity")
        if not user_id or not opportunity or not opportunity.get("id"):
            state.setdefault("errors", []).append("deadline_plan requires user_id and selected_opportunity.id.")
            return state
        tasks = compass_graph.create_deadline_plan(
            user_id=user_id,
            opportunity_id=opportunity["id"],
            today=date.fromisoformat(state.get("today") or date.today().isoformat()),
        )
        state["deadline_plan"] = tasks
        state["final_answer"] = "Created a deadline plan."
        return state

    def unsupported(state: AgentState) -> AgentState:
        state = {**state}
        state["final_answer"] = compass_graph.final_response.unsupported(state.get("intent") or "unknown")
        return state

    workflow.add_node("intent_router", route_intent)
    workflow.add_node("profile_update", profile_update)
    workflow.add_node("find_opportunities", find_opportunities)
    workflow.add_node("draft_document", draft_document)
    workflow.add_node("track_application", track_application)
    workflow.add_node("deadline_plan", deadline_plan)
    workflow.add_node("unsupported", unsupported)

    workflow.set_entry_point("intent_router")
    workflow.add_conditional_edges(
        "intent_router",
        route_by_intent,
        {
            "profile_update": "profile_update",
            "find_opportunities": "find_opportunities",
            "draft_document": "draft_document",
            "track_application": "track_application",
            "deadline_plan": "deadline_plan",
        },
    )
    workflow.add_edge("profile_update", END)
    workflow.add_edge("find_opportunities", END)
    workflow.add_edge("draft_document", END)
    workflow.add_edge("track_application", END)
    workflow.add_edge("deadline_plan", END)
    workflow.add_edge("unsupported", END)
    return workflow.compile()
