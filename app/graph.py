from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import date
from datetime import datetime, timezone
import time
from typing import Any

from agents.extraction_agent import OpportunityExtractionAgent
from agents.final_response_agent import FinalResponseAgent
from agents.image_extraction_agent import ImageExtractionAgent
from agents.intent_router import IntentRouter
from agents.deadline_planner_agent import DeadlinePlannerAgent
from agents.deadline_verifier_agent import DeadlineVerifierAgent
from agents.drafting_agent import DraftingAgent
from agents.eligibility_agent import EligibilityAgent
from agents.prioritization_agent import PrioritizationAgent
from tools.search_intent import (
    detect_opportunity_type_intent,
    is_opportunity_relevant,
    matches_location_intent,
    matches_opportunity_type_intent,
)
from tools.opportunity_type import normalize_opportunity_type
from tools.source_policy_gate import SourcePolicyGate
from agents.profile_agent import ProfileAgent
from agents.search_planner_agent import SearchPlannerAgent
from agents.source_verification_agent import SourceVerificationAgent
from agents.tracker_agent import TrackerAgent
from app.config import get_settings
from app.state import AgentState
from schemas.profile_schema import StudentProfile
from tools.dedup_tool import DeduplicationEngine
from tools.embedding_tool import EmbeddingTool
from tools.groq_tool import GroqClient
from tools.scraper_tool import WebScraper
from tools.supabase_tool import SupabaseRepository
from tools.upload_tool import UploadService
from tools.ocr_tool import OCRTool
from tools.web_search_tool import SearchProvider, build_search_provider


class CompassGraph:
    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        scraper: WebScraper | None = None,
        repository: SupabaseRepository | None = None,
        embedding_tool: EmbeddingTool | None = None,
        llm_client: GroqClient | None = None,
    ) -> None:
        self.settings = get_settings()
        self.intent_router = IntentRouter()
        self.profile_agent = ProfileAgent(client=llm_client) if llm_client else ProfileAgent()
        self.search_planner = SearchPlannerAgent(client=llm_client) if llm_client else SearchPlannerAgent()
        self.search_provider = search_provider or build_search_provider()
        self.scraper = scraper or WebScraper()
        self.extraction_agent = OpportunityExtractionAgent(client=llm_client) if llm_client else OpportunityExtractionAgent()
        self._image_extraction_agent: ImageExtractionAgent | None = None
        self.source_verification_agent = SourceVerificationAgent(client=llm_client) if llm_client else SourceVerificationAgent()
        self.deadline_verifier_agent = DeadlineVerifierAgent(
            search_provider=self.search_provider,
            scraper=self.scraper,
            client=llm_client,
        )
        self.eligibility_agent = EligibilityAgent(client=llm_client) if llm_client else EligibilityAgent()
        self.deduplication_engine = DeduplicationEngine()
        self.prioritization_agent = PrioritizationAgent(client=llm_client) if llm_client else PrioritizationAgent()
        self.deadline_planner_agent = DeadlinePlannerAgent()
        self.drafting_agent = DraftingAgent(client=llm_client) if llm_client else DraftingAgent()
        self.tracker_agent = TrackerAgent()
        self.ocr_tool = OCRTool()
        self.repository = repository or SupabaseRepository()
        self.embedding_tool = embedding_tool or EmbeddingTool()
        self._upload_service: UploadService | None = None
        self.final_response = FinalResponseAgent()

    @property
    def image_extraction_agent(self) -> ImageExtractionAgent:
        if self._image_extraction_agent is None:
            self._image_extraction_agent = ImageExtractionAgent()
        return self._image_extraction_agent

    @property
    def upload_service(self) -> UploadService:
        if self._upload_service is None:
            self._upload_service = UploadService(self.repository)
        return self._upload_service

    def invoke(self, initial_state: AgentState) -> AgentState:
        from app.langgraph_workflow import build_langgraph

        return build_langgraph(self).invoke(initial_state)

    def _profile_update(self, state: AgentState) -> AgentState:
        existing = self._profile_from_state(state.get("profile", {}))
        profile = self.profile_agent.update_profile(existing, state["user_query"])
        profile_dict = profile.model_dump()
        state["profile"] = profile_dict
        state["search_queries"] = self.search_planner.plan(profile_dict, self._today(state), state.get("user_query"))
        state["final_answer"] = self.final_response.profile_updated(profile_dict, state["search_queries"])
        return state

    def update_profile_only(self, user_id: str, text: str, existing_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        existing = self._profile_from_state(existing_profile or {})
        profile = self.profile_agent.update_profile(existing, text)
        profile_dict = profile.model_dump()
        saved = self.repository.save_profile(user_id, profile_dict)
        return {"profile": profile_dict, "saved_profile": saved}

    def create_search_job(self, user_id: str, query: str, profile: dict[str, Any], max_results_per_query: int = 3) -> dict[str, Any]:
        return self.repository.create_search_job(
            user_id=user_id,
            query=query,
            profile={**profile, "_max_results_per_query": max_results_per_query},
        )

    def get_search_job(self, user_id: str, job_id: str) -> dict[str, Any] | None:
        return self.repository.get_search_job(user_id=user_id, job_id=job_id)

    def list_search_jobs(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.list_search_jobs(user_id=user_id, limit=limit)

    def cancel_search_job(self, user_id: str, job_id: str) -> dict[str, Any]:
        return self.repository.cancel_search_job(user_id, job_id)

    def retry_search_job(self, user_id: str, job_id: str) -> dict[str, Any]:
        return self.repository.retry_search_job(user_id, job_id)

    def delete_search_job(self, user_id: str, job_id: str) -> dict[str, Any]:
        return self.repository.delete_search_job(user_id, job_id)

    def run_search_job(self, job_id: str, user_id: str, query: str, profile: dict[str, Any], max_results_per_query: int = 3) -> None:
        started_at = datetime.now(timezone.utc).isoformat()
        existing_job = self.repository.get_search_job_by_id(job_id) or {}
        self.repository.update_search_job(
            job_id,
            status="running",
            progress_message="Planning search queries",
            current_stage="planning",
            started_at=started_at,
        )
        try:
            result = self.invoke(
                {
                    "search_job_id": job_id,
                    "search_started_at": time.monotonic(),
                    "stage_payload": existing_job.get("stage_payload") or {},
                    "user_id": user_id,
                    "user_query": query,
                    "profile": profile,
                    "max_results_per_query": max_results_per_query,
                    "today": date.today().isoformat(),
                    "errors": [],
                }
            )
            current = self.repository.get_search_job_by_id(job_id)
            if current and current.get("status") in {"failed", "cancelled"}:
                return
            payload = {
                "answer": result["final_answer"],
                "queries": result.get("search_queries", []),
                "opportunities": result.get("prioritized_opportunities", []),
                "errors": result.get("errors", []),
            }
            self.repository.update_search_job(
                job_id,
                status="completed",
                progress_message="Search completed",
                current_stage="completed",
                result=payload,
                error=None,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        except TimeoutError as exc:
            if not self._complete_search_job_with_partial(job_id, str(exc)):
                self.repository.fail_search_job(
                    job_id,
                    str(exc),
                    progress_message="Search timed out",
                )
            raise
        except Exception as exc:
            current = self.repository.get_search_job_by_id(job_id)
            if current and current.get("status") == "cancelled":
                return
            self.repository.fail_search_job(
                job_id,
                str(exc),
                progress_message="Search failed",
            )
            raise

    def _update_search_job(self, state: AgentState, progress_message: str, **updates: Any) -> None:
        job_id = state.get("search_job_id")
        if not job_id:
            return
        self.repository.update_search_job(job_id, progress_message=progress_message, **updates)

    def _check_search_timeout(self, state: AgentState) -> None:
        job_id = state.get("search_job_id")
        if job_id:
            current = self.repository.get_search_job_by_id(job_id)
            if current and current.get("status") == "cancelled":
                raise RuntimeError("Search cancelled by user.")
        started_at = state.get("search_started_at")
        if started_at is None:
            return
        if time.monotonic() - float(started_at) > self.settings.search_job_timeout_seconds:
            raise TimeoutError("Search job exceeded the maximum allowed runtime.")

    def _persist_search_partial(self, state: AgentState, *, stage: str, progress_message: str, **payload: Any) -> None:
        job_id = state.get("search_job_id")
        if not job_id:
            return
        current = self.repository.get_search_job_by_id(job_id) or {}
        result = current.get("result") or {}
        stage_payload = {**(current.get("stage_payload") or {}), **payload}
        updates = {
            "current_stage": stage,
            "progress_message": progress_message,
            "stage_payload": stage_payload,
            "result": {**result, **self._search_result_summary(stage_payload, state)},
        }
        if hasattr(self.repository, "update_search_stage"):
            self.repository.update_search_stage(job_id, **updates)
        else:
            self.repository.update_search_job(job_id, **updates)
        state["stage_payload"] = stage_payload

    def _complete_search_job_with_partial(self, job_id: str, error: str) -> bool:
        current = self.repository.get_search_job_by_id(job_id) or {}
        result = current.get("result") or {}
        stage_payload = current.get("stage_payload") or {}
        partial = {
            **result,
            "queries": result.get("queries") or stage_payload.get("search_queries") or [],
            "raw_result_count": result.get("raw_result_count") or len(stage_payload.get("raw_search_results") or []),
            "candidate_count": result.get("candidate_count") or len(stage_payload.get("candidates") or []),
            "extracted_count": result.get("extracted_count") or len(stage_payload.get("extracted_opportunities") or []),
            "deduplicated_count": result.get("deduplicated_count") or len(stage_payload.get("deduplicated_opportunities") or []),
            "ranked_count": result.get("ranked_count") or len(stage_payload.get("prioritized_opportunities") or []),
            "opportunities": (
                result.get("opportunities")
                or stage_payload.get("saved_opportunities")
                or stage_payload.get("prioritized_opportunities")
                or stage_payload.get("deduplicated_opportunities")
                or stage_payload.get("extracted_opportunities")
                or []
            ),
        }
        if not partial["opportunities"]:
            return False
        errors = list(partial.get("errors") or [])
        errors.append(error)
        partial["errors"] = errors
        partial["answer"] = "Search timed out, so Compass returned the opportunities found so far."
        self.repository.update_search_job(
            job_id,
            status="completed",
            current_stage="completed",
            progress_message=f"Search timed out; returned {len(partial['opportunities'])} partial result(s)",
            result=partial,
            error=error,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return True

    @staticmethod
    def _search_result_summary(stage_payload: dict[str, Any], state: AgentState) -> dict[str, Any]:
        return {
            "queries": stage_payload.get("search_queries") or state.get("search_queries") or [],
            "raw_result_count": len(stage_payload.get("raw_search_results") or []),
            "candidate_count": len(stage_payload.get("candidates") or []),
            "extracted_count": len(stage_payload.get("extracted_opportunities") or []),
            "deduplicated_count": len(stage_payload.get("deduplicated_opportunities") or []),
            "ranked_count": len(stage_payload.get("prioritized_opportunities") or []),
            "opportunities": (
                stage_payload.get("saved_opportunities")
                or stage_payload.get("prioritized_opportunities")
                or stage_payload.get("deduplicated_opportunities")
                or stage_payload.get("extracted_opportunities")
                or []
            ),
            "errors": state.get("errors", []),
        }

    def _plan_search_queries(self, profile_dict: dict[str, Any], today: date, user_query: str | None = None) -> list[str]:
        timeout = self.settings.search_planning_timeout_seconds
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.search_planner.plan, profile_dict, today, user_query)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError as exc:
                raise TimeoutError(f"Search planning timed out after {timeout} seconds.") from exc

    def _find_opportunities(self, state: AgentState) -> AgentState:
        state.setdefault("errors", [])
        stage_payload = state.setdefault("stage_payload", {})
        self._update_search_job(state, "Planning search queries")
        try:
            profile = self._profile_from_state(state.get("profile", {}))
            if not any(profile.model_dump().values()):
                profile = self.profile_agent.update_profile(profile, state["user_query"])
            profile_dict = profile.model_dump()
            state["profile"] = profile_dict
            if stage_payload.get("search_queries"):
                state["search_queries"] = stage_payload["search_queries"]
            else:
                state["search_queries"] = self._plan_search_queries(
                    profile_dict,
                    self._today(state),
                    state.get("user_query"),
                )[: self.search_planner.settings.search_query_limit]
                self._persist_search_partial(
                    state,
                    stage="planned",
                    progress_message=f"Planned {len(state['search_queries'])} search queries",
                    search_queries=state["search_queries"],
                )
                stage_payload = state["stage_payload"]
            self._update_search_job(state, f"Planned {len(state['search_queries'])} search queries")
        except Exception as exc:
            self._record_error(state, "search planning", exc)
            progress = "Search planning timed out" if isinstance(exc, TimeoutError) else f"Search planning failed: {exc}"
            self._update_search_job(
                state,
                progress,
                status="failed",
                error=str(exc),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            state["search_queries"] = []
            state["raw_search_results"] = []
            state["candidates"] = []
            state["deduplicated_opportunities"] = []
            state["prioritized_opportunities"] = []
            state["final_answer"] = self.final_response.search_results([])
            return state

        self._check_search_timeout(state)
        if stage_payload.get("raw_search_results"):
            state["raw_search_results"] = stage_payload["raw_search_results"]
        else:
            self._update_search_job(state, "Searching trusted sources", current_stage="searching")
            state["raw_search_results"] = self._search(state["search_queries"], state)
            state["raw_search_results"] = SourcePolicyGate.rank_search_results(
                state["raw_search_results"],
                min_results=self.settings.search_min_results,
            )
            state["raw_search_results"] = state["raw_search_results"][: self.settings.search_candidate_limit]
            self._persist_search_partial(
                state,
                stage="searched",
                progress_message=f"Found {len(state['raw_search_results'])} trusted source candidates",
                raw_search_results=state["raw_search_results"],
            )
            stage_payload = state["stage_payload"]
        self._check_search_timeout(state)
        if stage_payload.get("candidates"):
            state["candidates"] = stage_payload["candidates"]
        else:
            self._update_search_job(state, "Scraping source pages", current_stage="scraping")
            state["candidates"] = self._build_candidates(state["raw_search_results"], state)
            self._persist_search_partial(
                state,
                stage="scraped",
                progress_message=f"Prepared {len(state['candidates'])} source pages",
                candidates=state["candidates"],
            )
            stage_payload = state["stage_payload"]
        self._check_search_timeout(state)
        if stage_payload.get("extracted_opportunities"):
            extracted = stage_payload["extracted_opportunities"]
        else:
            self._update_search_job(state, "Extracting opportunity details", current_stage="extracting")
            extracted = self._extract_verify_and_filter(
                state["candidates"],
                profile_dict,
                self._today(state),
                state,
                user_query=state.get("user_query"),
            )
            self._persist_search_partial(
                state,
                stage="extracted",
                progress_message=f"Extracted {len(extracted)} opportunity records",
                extracted_opportunities=extracted,
            )
            stage_payload = state["stage_payload"]
        self._check_search_timeout(state)
        if stage_payload.get("deduplicated_opportunities"):
            state["deduplicated_opportunities"] = stage_payload["deduplicated_opportunities"]
        else:
            self._update_search_job(state, "Verifying source trust and deduplicating results", current_stage="deduplicating")
            state["deduplicated_opportunities"] = self.deduplication_engine.merge(extracted)
            self._persist_search_partial(
                state,
                stage="deduplicated",
                progress_message=f"Deduplicated to {len(state['deduplicated_opportunities'])} opportunities",
                extracted_opportunities=extracted,
                deduplicated_opportunities=state["deduplicated_opportunities"],
            )
            stage_payload = state["stage_payload"]
        self._update_search_job(state, f"Deduplicated to {len(state['deduplicated_opportunities'])} opportunities")
        self._check_search_timeout(state)
        if stage_payload.get("prioritized_opportunities"):
            state["prioritized_opportunities"] = stage_payload["prioritized_opportunities"]
        else:
            try:
                self._update_search_job(state, "Ranking opportunities", current_stage="ranking")
                state["prioritized_opportunities"] = self.prioritization_agent.rank(
                    state["deduplicated_opportunities"],
                    user_query=state.get("user_query"),
                )
            except Exception as exc:
                self._record_error(state, "opportunity ranking", exc)
                state["prioritized_opportunities"] = state["deduplicated_opportunities"]
            self._persist_search_partial(
                state,
                stage="ranked",
                progress_message=f"Ranked {len(state['prioritized_opportunities'])} opportunities",
                prioritized_opportunities=state["prioritized_opportunities"],
            )
            stage_payload = state["stage_payload"]
        self._update_search_job(state, f"Saving {len(state['prioritized_opportunities'])} opportunities", current_stage="saving")
        if stage_payload.get("saved_opportunities"):
            state["prioritized_opportunities"] = stage_payload["saved_opportunities"]
        else:
            state["prioritized_opportunities"] = self._save_opportunities(state["prioritized_opportunities"], state)
            self._persist_search_partial(
                state,
                stage="saved",
                progress_message=f"Saved {len(state['prioritized_opportunities'])} opportunities",
                saved_opportunities=state["prioritized_opportunities"],
            )
        self._update_search_job(state, f"Saved {len(state['prioritized_opportunities'])} opportunities")
        state["final_answer"] = self.final_response.search_results(state["prioritized_opportunities"])
        return state

    def save_opportunity(
        self,
        user_id: str,
        *,
        opportunity_id: str | None = None,
        opportunity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.repository.save_opportunity_for_user_record(
            user_id,
            opportunity_id=opportunity_id,
            opportunity=opportunity,
        )

    def unsave_opportunity(self, user_id: str, opportunity_id: str) -> dict[str, Any]:
        return self.repository.unsave_opportunity_for_user(user_id, opportunity_id)

    def get_opportunity(self, opportunity_id: str) -> dict[str, Any]:
        return self.repository.get_opportunity(opportunity_id)

    def list_opportunities(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_saved_opportunities(user_id=user_id, limit=limit)

    def list_documents(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_documents(user_id=user_id, limit=limit)

    def list_uploaded_files(self, user_id: str, purpose: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_uploaded_files(user_id=user_id, purpose=purpose, limit=limit)

    def list_tracker_items(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_tracker_items(user_id=user_id, limit=limit)

    def list_eval_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.repository.list_eval_runs(limit=limit)

    def list_source_flags(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.repository.list_source_flags(limit=limit)

    def get_notification_preferences(self, user_id: str) -> dict[str, Any] | None:
        return self.repository.get_notification_preferences(user_id)

    def update_notification_preferences(
        self,
        user_id: str,
        email_enabled: bool,
        reminder_days: list[int],
        notification_email: str | None = None,
    ) -> dict[str, Any]:
        return self.repository.upsert_notification_preferences(
            {
                "user_id": user_id,
                "email_enabled": email_enabled,
                "notification_email": notification_email,
                "reminder_days": reminder_days,
            }
        )

    def create_deadline_plan(self, user_id: str, opportunity_id: str, today: date | None = None) -> list[dict[str, Any]]:
        opportunity = self.repository.get_opportunity(opportunity_id)
        tasks = self.deadline_planner_agent.create_plan(opportunity, today or date.today())
        tasks = [{**task, "user_id": user_id} for task in tasks]
        return self.repository.save_application_tasks(tasks)

    def verify_deadline(self, opportunity_id: str) -> dict[str, Any]:
        opportunity = self.repository.get_opportunity(opportunity_id)
        result = self.deadline_verifier_agent.verify(opportunity)
        saved = self.repository.update_opportunity_deadline_verification(opportunity["id"], result)
        return {"deadline_verification": result, "opportunity": saved}

    def draft_document(
        self,
        user_id: str,
        profile: dict[str, Any],
        opportunity_id: str,
        document_type: str,
        cv_text: str | None = None,
        uploaded_file_id: str | None = None,
        regeneration_instruction: str | None = None,
        parent_document_id: str | None = None,
    ) -> dict[str, Any]:
        opportunity = self.repository.get_opportunity(opportunity_id)
        upload_context: dict[str, Any] | None = None
        if uploaded_file_id:
            upload_context = self.repository.get_uploaded_file(user_id, uploaded_file_id)
            extracted_text = upload_context.get("extracted_text")
            if not extracted_text:
                raise ValueError("Selected upload does not have extracted text.")
            cv_text = str(extracted_text)
        draft = self.drafting_agent.draft(
            profile,
            opportunity,
            document_type,
            cv_text,
            regeneration_instruction=regeneration_instruction,
        )
        return self.repository.save_generated_document(
            {
                "user_id": user_id,
                "opportunity_id": opportunity_id,
                "parent_document_id": parent_document_id,
                "version_number": self.repository.next_document_version(user_id, parent_document_id),
                "regeneration_instruction": regeneration_instruction,
                "source_upload_id": uploaded_file_id,
                **draft,
            }
        )

    def update_document(self, user_id: str, document_id: str, content: str) -> dict[str, Any]:
        return self.repository.update_generated_document(user_id, document_id, content)

    def update_tracker(
        self,
        user_id: str,
        text: str,
        opportunity_id: str | None = None,
    ) -> dict[str, Any]:
        action = self.tracker_agent.parse_update(text, opportunity_id)
        return self.repository.update_tracker(user_id, action)

    def update_tracker_status(self, user_id: str, task_id: str, status: str) -> dict[str, Any]:
        return self.repository.update_application_task_status(user_id, task_id, status)

    def extract_poster(self, user_id: str, file_name: str, file_obj: Any) -> dict[str, Any]:
        temp_path, mime_type = self.upload_service.persist_temp_file(file_name, file_obj)
        if mime_type not in self.upload_service.IMAGE_TYPES:
            temp_path.unlink(missing_ok=True)
            raise ValueError(f"Unsupported poster type: {mime_type}")
        try:
            with temp_path.open("rb") as stored_file:
                upload = self.upload_service.save_upload(
                    user_id=user_id,
                    file_name=file_name,
                    file_obj=stored_file,
                    bucket=self.upload_service.settings.poster_bucket,
                )
            extracted = self.image_extraction_agent.extract_from_image(temp_path, mime_type)
            file_record = self.repository.save_uploaded_file(
                {
                    "user_id": user_id,
                    "bucket": upload["bucket"],
                    "path": upload["path"],
                    "original_filename": file_name,
                    "mime_type": mime_type,
                    "size_bytes": upload["size_bytes"],
                    "purpose": "poster",
                    "extracted_text": None,
                    "extracted_json": extracted,
                }
            )
            return {"file": file_record, "extracted": extracted}
        finally:
            temp_path.unlink(missing_ok=True)

    def upload_document(self, user_id: str, file_name: str, file_obj: Any, purpose: str = "cv") -> dict[str, Any]:
        temp_path, mime_type = self.upload_service.persist_temp_file(file_name, file_obj)
        if mime_type not in self.upload_service.DOCUMENT_TYPES:
            temp_path.unlink(missing_ok=True)
            raise ValueError(f"Unsupported document type: {mime_type}")
        try:
            parsed = self.upload_service.extract_document_text(temp_path, mime_type)
            with temp_path.open("rb") as stored_file:
                upload = self.upload_service.save_upload(
                    user_id=user_id,
                    file_name=file_name,
                    file_obj=stored_file,
                    bucket=self.upload_service.settings.document_bucket,
                )
            extracted_text = parsed.get("ocr_text") or parsed["text"]
            file_record = self.repository.save_uploaded_file(
                {
                    "user_id": user_id,
                    "bucket": upload["bucket"],
                    "path": upload["path"],
                    "original_filename": file_name,
                    "mime_type": mime_type,
                    "size_bytes": upload["size_bytes"],
                    "purpose": purpose,
                    "extracted_text": extracted_text,
                    "extracted_json": {"needs_ocr": parsed.get("needs_ocr", False)},
                }
            )
            return {"file": file_record, "text": extracted_text}
        finally:
            temp_path.unlink(missing_ok=True)

    def ocr_diagnostics(self) -> dict[str, str]:
        return self.ocr_tool.diagnostics()

    def _search(self, queries: list[str], state: AgentState | None = None) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        results: list[dict[str, Any]] = []
        max_results = int(state.get("max_results_per_query") or self.settings.search_min_results) if state else self.settings.search_min_results

        def search_one(query: str) -> list[dict[str, Any]]:
            search_results = self.search_provider.search(query, max_results=max_results)
            batch: list[dict[str, Any]] = []
            for result in search_results:
                result_dict = result.model_dump(mode="json")
                result_dict["query"] = query
                batch.append(result_dict)
            return batch

        workers = min(max(1, self.settings.max_parallel_model_calls), len(queries))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(search_one, query): query for query in queries}
            for future in as_completed(futures):
                query = futures[future]
                try:
                    for result_dict in future.result():
                        url = result_dict["url"]
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        results.append(result_dict)
                except Exception as exc:
                    if state is not None:
                        self._record_error(state, f"web search for '{query}'", exc)
        return results

    def _build_candidates(self, results: list[dict[str, Any]], state: AgentState | None = None) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for result in results:
            try:
                source_payload = self._source_payload(result)
            except Exception as exc:
                if state is not None:
                    self._record_error(state, f"source fetch for {result['url']}", exc)
                continue
            candidates.append(
                {
                    "source_url": result["url"],
                    "source_title": result["title"],
                    "title": result["title"],
                    "snippet": result.get("snippet", ""),
                    "source": result.get("source", "web"),
                    "page_text": source_payload.get("text", ""),
                    "table_data": source_payload.get("table_data", ""),
                    "content_type": source_payload.get("content_type", "link_only"),
                    "source_tier": source_payload.get("tier", "C"),
                    "reason": source_payload.get("reason"),
                    "domain": source_payload.get("domain"),
                }
            )
        return candidates

    def _source_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        return self.scraper.scrape_page(
            result["url"],
            search_query=result.get("query"),
            title=result.get("title"),
        )

    def _process_candidate(
        self,
        candidate: dict[str, Any],
        profile: dict[str, Any],
        today: date,
        user_query: str | None = None,
    ) -> dict[str, Any] | None:
        extracted = self.extraction_agent.extract(candidate)
        extracted["source_tier"] = candidate["source_tier"]
        extracted["_source_url"] = candidate["source_url"]
        extracted["_source_content_type"] = candidate["content_type"]
        extracted["_source_reason"] = candidate.get("reason")
        if user_query and not is_opportunity_relevant(user_query, extracted):
            return None
        if user_query and not matches_location_intent(user_query, extracted):
            return None
        if user_query and not matches_opportunity_type_intent(
            detect_opportunity_type_intent(user_query),
            extracted,
        ):
            return None
        step_pause = self.settings.search_extraction_step_pause_seconds
        if step_pause > 0:
            time.sleep(step_pause)
        extracted["verification"] = self.source_verification_agent.verify(extracted, candidate)
        if self.deadline_verifier_agent.should_verify(extracted):
            try:
                deadline_verification = self.deadline_verifier_agent.verify(
                    extracted,
                    max_queries=10,
                    max_results_per_query=3,
                )
                extracted["verification"]["deadline_verification"] = deadline_verification
                if deadline_verification.get("deadline") and deadline_verification.get("status") in {"verified", "estimated"}:
                    extracted["deadline"] = deadline_verification["deadline"]
            except Exception as exc:
                notes = extracted["verification"].setdefault("notes", [])
                notes.append(f"Deadline verifier skipped: {exc.__class__.__name__}")
        if step_pause > 0:
            time.sleep(step_pause)
        extracted["eligibility_result"] = self.eligibility_agent.evaluate(profile, extracted, today)
        if extracted["eligibility_result"]["deadline_passed"]:
            return None
        return extracted

    def _extract_verify_and_filter(
        self,
        candidates: list[dict[str, Any]],
        profile: dict[str, Any],
        today: date,
        state: AgentState | None = None,
        user_query: str | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        opportunities: list[dict[str, Any]] = []
        pause = self.settings.search_extraction_pause_seconds
        for index, candidate in enumerate(candidates):
            self._check_search_timeout(state or {})
            if index > 0 and pause > 0:
                time.sleep(pause)
                self._check_search_timeout(state or {})
            try:
                extracted = self._process_candidate(candidate, profile, today, user_query=user_query)
                if extracted is not None:
                    opportunities.append(extracted)
                    if state is not None:
                        self._persist_search_partial(
                            state,
                            stage="extracting",
                            progress_message=f"Extracted {len(opportunities)} opportunity record(s)",
                            extracted_opportunities=opportunities,
                        )
            except TimeoutError:
                raise
            except Exception as exc:
                if state is not None:
                    self._record_error(state, f"candidate extraction for {candidate['source_url']}", exc)
            self._check_search_timeout(state or {})
        return opportunities

    def _save_opportunities(self, opportunities: list[dict[str, Any]], state: AgentState | None = None) -> list[dict[str, Any]]:
        saved_opportunities: list[dict[str, Any]] = []
        for opportunity in opportunities:
            try:
                match_snapshot = {**opportunity}
                match_fields = {
                    key: match_snapshot.get(key)
                    for key in ("eligibility_result", "priority", "priority_score")
                    if key in match_snapshot
                }
                source_tier = opportunity.pop("source_tier", "C")
                source_url = opportunity.pop("_source_url", str(opportunity.get("application_url")))
                source_content_type = opportunity.pop("_source_content_type", "link_only")
                source_reason = opportunity.pop("_source_reason", None)
                opportunity.pop("ranking_reason", None)
                for user_specific_key in ("eligibility_result", "priority", "priority_score"):
                    opportunity.pop(user_specific_key, None)
                opportunity["opportunity_type"] = normalize_opportunity_type(
                    opportunity,
                    state.get("user_query") if state else None,
                )
                source_rows = [
                    {
                        "url": source_url,
                        "source_tier": source_tier,
                        "content_type": source_content_type,
                        "extraction_status": "extracted",
                        "notes": source_reason or "; ".join(opportunity.get("extraction_notes") or []),
                    }
                ]
                embedding = None
                embeddings_enabled = bool(getattr(getattr(self.embedding_tool, "settings", None), "embeddings_enabled", False))
                if embeddings_enabled:
                    embedding = self.embedding_tool.embed_opportunity(opportunity)
                    existing_matches = self.repository.match_opportunities(embedding, threshold=0.9, limit=1)
                    if existing_matches:
                        existing_id = existing_matches[0]["opportunity_id"]
                        self.repository.add_opportunity_sources(existing_id, source_rows)
                        existing = self.repository.get_opportunity(existing_id)
                        user_id = state.get("user_id") if state else None
                        if user_id:
                            self.repository.save_user_opportunity_match(user_id, existing_id, match_snapshot)
                        saved_opportunities.append(
                            {
                                **existing,
                                **match_fields,
                                "source_tier": source_tier,
                                "dedup_similarity": existing_matches[0]["similarity"],
                            }
                        )
                        continue
                saved = self.repository.save_opportunity(
                    opportunity,
                    source_rows,
                )
                if embedding:
                    self.repository.save_opportunity_embedding(saved["id"], embedding)
                user_id = state.get("user_id") if state else None
                if user_id:
                    self.repository.save_user_opportunity_match(user_id, saved["id"], match_snapshot)
                saved_opportunities.append({**saved, **match_fields, "source_tier": source_tier})
            except Exception as exc:
                if state is not None:
                    title = opportunity.get("title") or opportunity.get("application_url") or "unknown opportunity"
                    self._record_error(state, f"opportunity save for {title}", exc)
        return saved_opportunities

    @staticmethod
    def _record_error(state: AgentState, stage: str, exc: Exception) -> None:
        state.setdefault("errors", []).append(f"{stage}: {exc}")

    @staticmethod
    def _profile_from_state(value: Any) -> StudentProfile:
        if isinstance(value, StudentProfile):
            return value
        if isinstance(value, dict):
            return StudentProfile.model_validate(value)
        return StudentProfile()

    @staticmethod
    def _today(state: AgentState) -> date:
        return date.fromisoformat(state.get("today") or date.today().isoformat())
