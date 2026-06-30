from typing import Any
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app.config import Settings, get_settings
from tools.retry_tool import with_backoff
from tools.short_id import (
    format_compass_user_id,
    generate_opportunity_id,
    normalize_opportunity_id,
    parse_compass_user_number,
)
from tools.opportunity_type import normalize_opportunity_type


class SupabaseRepository:
    """Thin storage boundary for Supabase persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        return self.settings.supabase_enabled

    def client(self) -> Any:
        if not self.enabled:
            return None
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise RuntimeError("supabase is required for database persistence.") from exc
            url, key = self.settings.require_supabase()
            self._client = create_client(url, key)
        return self._client

    def allocate_opportunity_id(self) -> str:
        for _ in range(64):
            candidate = generate_opportunity_id()
            rows = (
                self.client()
                .table("opportunities")
                .select("public_code")
                .eq("public_code", candidate)
                .limit(1)
                .execute()
                .data
            )
            if not rows:
                return candidate
        raise RuntimeError("Unable to allocate a unique opportunity id.")

    def save_opportunity(self, opportunity: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
        client = self.client()
        payload = {**opportunity}
        existing_code = payload.pop("public_code", None) or payload.pop("id", None)
        payload["public_code"] = normalize_opportunity_id(str(existing_code)) if existing_code else self.allocate_opportunity_id()
        saved = with_backoff(lambda: client.table("opportunities").insert(payload).execute()).data[0]
        source_rows = [{**source, "opportunity_id": saved["id"]} for source in sources]
        if source_rows:
            with_backoff(lambda: client.table("opportunity_sources").insert(source_rows).execute())
        return self._display_opportunity(saved)

    def add_opportunity_sources(self, opportunity_id: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not sources:
            return []
        internal_id = self.resolve_opportunity_internal_id(opportunity_id)
        rows = [{**source, "opportunity_id": internal_id} for source in sources]
        return with_backoff(
            lambda: self.client().table("opportunity_sources").upsert(rows, on_conflict="opportunity_id,url").execute()
        ).data

    def save_opportunity_embedding(self, opportunity_id: str, embedding: list[float]) -> dict[str, Any]:
        internal_id = self.resolve_opportunity_internal_id(opportunity_id)
        return (
            self.client()
            .table("opportunity_embeddings")
            .upsert({"opportunity_id": internal_id, "embedding": embedding})
            .execute()
            .data[0]
        )

    def match_opportunities(self, embedding: list[float], threshold: float = 0.88, limit: int = 5) -> list[dict[str, Any]]:
        return (
            self.client()
            .rpc("match_opportunities", {"query_embedding": embedding, "match_threshold": threshold, "match_count": limit})
            .execute()
            .data
        )

    def save_generated_document(self, document: dict[str, Any]) -> dict[str, Any]:
        if document.get("opportunity_id"):
            document = {**document, "opportunity_id": self.resolve_opportunity_internal_id(str(document["opportunity_id"]))}
        return self.client().table("generated_documents").insert(document).execute().data[0]

    def update_generated_document(self, user_id: str, document_id: str, content: str) -> dict[str, Any]:
        rows = (
            self.client()
            .table("generated_documents")
            .update({"content": content, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", document_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        if not rows:
            raise ValueError("Document not found.")
        return rows[0]

    def next_document_version(self, user_id: str, parent_document_id: str | None) -> int:
        if not parent_document_id:
            return 1
        rows = (
            self.client()
            .table("generated_documents")
            .select("version_number")
            .or_(f"id.eq.{parent_document_id},parent_document_id.eq.{parent_document_id}")
            .eq("user_id", user_id)
            .order("version_number", desc=True)
            .limit(1)
            .execute()
            .data
        )
        return int(rows[0].get("version_number") or 1) + 1 if rows else 2

    def save_application_task(self, task: dict[str, Any]) -> dict[str, Any]:
        display_opportunity_id = None
        if task.get("opportunity_id"):
            opportunity = self.get_opportunity(str(task["opportunity_id"]))
            display_opportunity_id = opportunity["id"]
            task = {**task, "opportunity_id": opportunity["internal_id"]}
        saved = self.client().table("application_tasks").insert(task).execute().data[0]
        return self._display_application_task(saved, display_opportunity_id=display_opportunity_id)

    def save_application_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not tasks:
            return []
        display_ids_by_internal_id: dict[str, str] = {}
        resolved_tasks = []
        for task in tasks:
            if task.get("opportunity_id"):
                opportunity = self.get_opportunity(str(task["opportunity_id"]))
                display_ids_by_internal_id[str(opportunity["internal_id"])] = str(opportunity["id"])
                resolved_tasks.append({**task, "opportunity_id": opportunity["internal_id"]})
            else:
                resolved_tasks.append(task)
        saved = self.client().table("application_tasks").insert(resolved_tasks).execute().data
        return [
            self._display_application_task(
                row,
                display_opportunity_id=display_ids_by_internal_id.get(str(row.get("opportunity_id"))),
            )
            for row in saved
        ]

    def save_opportunity_for_user(self, user_id: str, opportunity_id: str) -> dict[str, Any]:
        internal_id = self.resolve_opportunity_internal_id(opportunity_id)
        return (
            self.client()
            .table("saved_opportunities")
            .upsert({"user_id": user_id, "opportunity_id": internal_id}, on_conflict="user_id,opportunity_id")
            .execute()
            .data[0]
        )

    def unsave_opportunity_for_user(self, user_id: str, opportunity_id: str) -> dict[str, Any]:
        internal_id = self.resolve_opportunity_internal_id(opportunity_id)
        display_id = self.get_opportunity(opportunity_id)["id"]
        rows = (
            self.client()
            .table("saved_opportunities")
            .delete()
            .eq("user_id", user_id)
            .eq("opportunity_id", internal_id)
            .execute()
            .data
        )
        if not rows:
            raise ValueError(f"Saved opportunity not found: {display_id}")
        return {"opportunity_id": display_id, "removed": True}

    def save_opportunity_for_user_record(
        self,
        user_id: str,
        *,
        opportunity_id: str | None = None,
        opportunity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_id = opportunity_id or (opportunity or {}).get("public_code") or (opportunity or {}).get("id")
        if resolved_id:
            resolved_id = self.get_opportunity(str(resolved_id))["id"]
        if not resolved_id:
            if not opportunity:
                raise ValueError("An opportunity id or opportunity payload is required.")
            row, sources = self._prepare_opportunity_persistence(opportunity)
            saved = self.save_opportunity(row, sources)
            resolved_id = saved["id"]

        link = self.save_opportunity_for_user(user_id, resolved_id)
        if opportunity:
            self.save_user_opportunity_match(user_id, resolved_id, opportunity)
        saved_opportunity = self.get_opportunity(resolved_id)
        return {
            "saved_id": link["id"],
            "opportunity_id": resolved_id,
            "saved_at": link.get("created_at"),
            "opportunity": saved_opportunity,
        }

    def save_user_opportunity_match(
        self,
        user_id: str,
        opportunity_id: str,
        match: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "user_id": user_id,
            "opportunity_id": self.resolve_opportunity_internal_id(opportunity_id),
            "eligibility_result": match.get("eligibility_result"),
            "priority": match.get("priority"),
            "priority_score": match.get("priority_score"),
            "notes": match.get("ranking_reason") or match.get("summary"),
        }
        return (
            self.client()
            .table("user_opportunity_matches")
            .upsert(row, on_conflict="user_id,opportunity_id")
            .execute()
            .data[0]
        )

    def list_saved_opportunities(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            self.client()
            .table("saved_opportunities")
            .select("id, created_at, opportunity_id, opportunities(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        opportunities: list[dict[str, Any]] = []
        match_map: dict[str, dict[str, Any]] = {}
        try:
            match_rows = (
                self.client()
                .table("user_opportunity_matches")
                .select("opportunity_id, eligibility_result, priority, priority_score, notes")
                .eq("user_id", user_id)
                .limit(200)
                .execute()
                .data
            )
            match_map = {row["opportunity_id"]: row for row in match_rows if row.get("opportunity_id")}
        except Exception:
            match_map = {}
        for row in rows:
            opportunity = row.get("opportunities")
            if not opportunity:
                continue
            opportunity = self._display_opportunity(opportunity)
            user_match = match_map.get(row["opportunity_id"], {})
            opportunities.append(
                {
                    **opportunity,
                    **{key: value for key, value in user_match.items() if key != "opportunity_id"},
                    "saved_id": row["id"],
                    "saved_at": row.get("created_at"),
                }
            )
        return opportunities

    @staticmethod
    def _prepare_opportunity_persistence(opportunity: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        row = {
            key: opportunity.get(key)
            for key in (
                "title",
                "provider",
                "country",
                "opportunity_type",
                "deadline",
                "funding_type",
                "eligibility",
                "required_documents",
                "application_url",
                "contact_email",
                "summary",
                "payment_requested",
                "warnings",
                "extraction_notes",
                "verification",
            )
            if key in opportunity
        }
        if not row.get("title"):
            raise ValueError("Opportunity title is required to save.")
        row["opportunity_type"] = normalize_opportunity_type(opportunity)

        source_url = opportunity.get("application_url") or opportunity.get("_source_url")
        sources: list[dict[str, Any]] = []
        if source_url:
            sources.append(
                {
                    "url": str(source_url),
                    "source_tier": opportunity.get("source_tier", "C"),
                    "content_type": opportunity.get("_source_content_type", "link_only"),
                    "extraction_status": "extracted",
                    "notes": opportunity.get("_source_reason"),
                }
            )
        return row, sources

    def get_opportunity(self, opportunity_id: str) -> dict[str, Any]:
        query = self.client().table("opportunities").select("*")
        if self._is_uuid(opportunity_id):
            query = query.eq("id", opportunity_id)
        else:
            query = query.eq("public_code", normalize_opportunity_id(opportunity_id))
        rows = query.limit(1).execute().data
        if not rows:
            raise ValueError(f"Opportunity not found: {opportunity_id}")
        return self._display_opportunity(rows[0])

    def resolve_opportunity_internal_id(self, opportunity_id: str) -> str:
        if self._is_uuid(str(opportunity_id)):
            return str(opportunity_id)
        return str(self.get_opportunity(opportunity_id)["internal_id"])

    def update_opportunity_deadline_verification(self, opportunity_id: str, verification: dict[str, Any]) -> dict[str, Any]:
        opportunity = self.get_opportunity(opportunity_id)
        current_verification = opportunity.get("verification") or {}
        payload: dict[str, Any] = {
            "verification": {
                **current_verification,
                "deadline_verification": verification,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        deadline = verification.get("deadline")
        if deadline and verification.get("status") in {"verified", "estimated"} and self._is_current_or_future_date(deadline):
            payload["deadline"] = deadline
        elif opportunity.get("deadline") and not self._is_current_or_future_date(opportunity["deadline"]):
            payload["deadline"] = None
        rows = (
            self.client()
            .table("opportunities")
            .update(payload)
            .eq("id", opportunity["internal_id"])
            .execute()
            .data
        )
        if not rows:
            raise ValueError(f"Opportunity not found: {opportunity_id}")
        return self._display_opportunity(rows[0])

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            UUID(str(value))
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_current_or_future_date(value: object) -> bool:
        try:
            return date.fromisoformat(str(value)[:10]) >= date.today()
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _display_opportunity(row: dict[str, Any]) -> dict[str, Any]:
        if not row:
            return row
        public_code = row.get("public_code") or row.get("id")
        return {**row, "internal_id": row.get("id"), "id": public_code}

    def get_cached_source_page(self, url: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        rows = (
            self.client()
            .table("source_pages")
            .select("*")
            .eq("url", url)
            .gt("expires_at", now)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    def get_cached_search_results(self, query: str, provider: str) -> list[dict[str, Any]] | None:
        now = datetime.now(timezone.utc).isoformat()
        rows = (
            self.client()
            .table("search_cache")
            .select("*")
            .eq("query", query)
            .eq("provider", provider)
            .gt("expires_at", now)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return None
        return rows[0].get("results") or []

    def save_search_results_cache(
        self,
        query: str,
        provider: str,
        results: list[dict[str, Any]],
        ttl_hours: int = 12,
    ) -> dict[str, Any]:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        row = {
            "query": query,
            "provider": provider,
            "results": results,
            "expires_at": expires_at.isoformat(),
        }
        return self.client().table("search_cache").upsert(row, on_conflict="query").execute().data[0]

    def save_source_page(self, page: dict[str, Any], ttl_hours: int = 48) -> dict[str, Any]:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        row = {
            "url": page["url"],
            "content_type": page["content_type"],
            "source_tier": page["tier"],
            "text": page.get("text"),
            "expires_at": expires_at.isoformat(),
        }
        return self.client().table("source_pages").upsert(row, on_conflict="url").execute().data[0]

    def allocate_compass_user_id(self) -> str:
        rows = self.client().table("student_profiles").select("compass_user_id").execute().data
        highest = 0
        for row in rows:
            compass_user_id = row.get("compass_user_id")
            if not compass_user_id:
                continue
            number = parse_compass_user_number(str(compass_user_id))
            if number is not None:
                highest = max(highest, number)
        for offset in range(1, 1000):
            candidate = format_compass_user_id(highest + offset)
            existing = (
                self.client()
                .table("student_profiles")
                .select("user_id")
                .eq("compass_user_id", candidate)
                .limit(1)
                .execute()
                .data
            )
            if not existing:
                return candidate
        raise RuntimeError("Unable to allocate a Compass user id.")

    def ensure_compass_user_id(self, user_id: str) -> str:
        profile = self.get_profile(user_id)
        if profile and profile.get("compass_user_id"):
            return str(profile["compass_user_id"])
        for _ in range(5):
            candidate = self.allocate_compass_user_id()
            payload = {"user_id": user_id, "compass_user_id": candidate}
            saved = (
                self.client()
                .table("student_profiles")
                .upsert(payload, on_conflict="user_id")
                .execute()
                .data[0]
            )
            if saved.get("compass_user_id"):
                return str(saved["compass_user_id"])
            profile = self.get_profile(user_id)
            if profile and profile.get("compass_user_id"):
                return str(profile["compass_user_id"])
        raise RuntimeError("Unable to ensure Compass user id.")

    def save_profile(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in profile.items() if key != "compass_user_id"}
        compass_user_id = self.ensure_compass_user_id(user_id)
        return (
            self.client()
            .table("student_profiles")
            .upsert({"user_id": user_id, "compass_user_id": compass_user_id, **payload}, on_conflict="user_id")
            .execute()
            .data[0]
        )

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        rows = (
            self.client()
            .table("student_profiles")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    def update_tracker(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "user_id": user_id,
            "title": payload.get("next_task") or f"Application status: {payload['status']}",
            **payload,
        }
        display_opportunity_id = None
        if row.get("opportunity_id"):
            opportunity = self.get_opportunity(str(row["opportunity_id"]))
            display_opportunity_id = opportunity["id"]
            row["opportunity_id"] = opportunity["internal_id"]
        saved = self.client().table("application_tasks").insert(row).execute().data[0]
        return self._display_application_task(saved, display_opportunity_id=display_opportunity_id)

    def update_application_task_status(self, user_id: str, task_id: str, status: str) -> dict[str, Any]:
        normalized_status = " ".join(str(status).strip().lower().replace("_", " ").split())
        if normalized_status not in {"pending", "preparing", "submitted", "waiting", "result"}:
            raise ValueError("Unsupported tracker status.")
        query = (
            self.client()
            .table("application_tasks")
            .update({"status": normalized_status})
            .eq("user_id", user_id)
        )
        if self._is_uuid(task_id):
            query = query.eq("id", task_id)
        else:
            query = query.like("id", f"{task_id}%")
        rows = query.execute().data
        if not rows:
            raise ValueError("Tracker task not found.")
        return self._display_application_task(rows[0])

    def upload_file(self, bucket: str, path: str, content: bytes, content_type: str) -> dict[str, Any]:
        response = self.client().storage.from_(bucket).upload(
            path,
            content,
            {"content-type": content_type, "upsert": "false"},
        )
        return {"bucket": bucket, "path": path, "response": response}

    def save_uploaded_file(self, record: dict[str, Any]) -> dict[str, Any]:
        return self.client().table("uploaded_files").insert(record).execute().data[0]

    def list_uploaded_files(self, user_id: str, purpose: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = (
            self.client()
            .table("uploaded_files")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if purpose:
            query = query.eq("purpose", purpose)
        return query.execute().data

    def get_uploaded_file(self, user_id: str, file_id: str) -> dict[str, Any]:
        rows = (
            self.client()
            .table("uploaded_files")
            .select("*")
            .eq("id", file_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            raise ValueError("Uploaded file not found.")
        return rows[0]

    def is_admin_user(self, user_id: str) -> bool:
        rows = (
            self.client()
            .table("admin_users")
            .select("user_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
        return bool(rows)

    def save_eval_run(self, record: dict[str, Any]) -> dict[str, Any]:
        return self.client().table("eval_runs").insert(record).execute().data[0]

    def list_eval_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return (
            self.client()
            .table("eval_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    def list_source_flags(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            self.client()
            .table("opportunities")
            .select("id,public_code,title,provider,application_url,warnings,verification,created_at")
            .or_("payment_requested.eq.true,verification->>trust_level.eq.suspicious,verification->>trust_level.eq.needs_review")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return [self._display_opportunity(row) for row in rows]

    def list_opportunities(self, user_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if user_id:
            return self.list_saved_opportunities(user_id=user_id, limit=limit)
        rows = (
            self.client()
            .table("opportunities")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return [self._display_opportunity(row) for row in rows]

    def list_documents(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return (
            self.client()
            .table("generated_documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    def list_tracker_items(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            self.client()
            .table("application_tasks")
            .select("*, opportunities(public_code,title,provider,deadline)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        deliveries_by_task = self._reminder_deliveries_by_task_id([str(row["id"]) for row in rows if row.get("id")])
        return [
            self._display_application_task(
                row,
                reminder_deliveries=deliveries_by_task.get(str(row.get("id")), []),
            )
            for row in rows
        ]

    def _reminder_deliveries_by_task_id(self, task_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not task_ids:
            return {}
        try:
            rows = (
                self.client()
                .table("reminder_deliveries")
                .select("task_id, reminder_date, notification_email, sent_at")
                .in_("task_id", task_ids)
                .order("sent_at", desc=True)
                .execute()
                .data
            )
        except Exception:
            return {}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            task_id = str(row.get("task_id") or "")
            if not task_id:
                continue
            grouped.setdefault(task_id, []).append(row)
        return grouped

    @staticmethod
    def _display_application_task(
        row: dict[str, Any],
        *,
        display_opportunity_id: str | None = None,
        reminder_deliveries: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not row:
            return row
        internal_id = row.get("id")
        task_code = str(internal_id or "").replace("-", "")[:8] or str(internal_id or "")
        opportunity = row.get("opportunities") or {}
        opportunity_code = display_opportunity_id or opportunity.get("public_code") or row.get("opportunity_id")
        deliveries = reminder_deliveries or []
        latest_delivery = deliveries[0] if deliveries else {}
        return {
            **{key: value for key, value in row.items() if key != "opportunities"},
            "internal_id": internal_id,
            "id": task_code,
            "task_code": task_code,
            "opportunity_id": opportunity_code,
            "opportunity": opportunity or None,
            "email_status": {
                "sent": bool(deliveries),
                "status": "sent" if deliveries else "not_sent",
                "sent_count": len(deliveries),
                "sent_at": latest_delivery.get("sent_at"),
                "notification_email": latest_delivery.get("notification_email"),
                "reminder_date": latest_delivery.get("reminder_date"),
            },
        }

    def get_notification_preferences(self, user_id: str) -> dict[str, Any] | None:
        rows = (
            self.client()
            .table("notification_preferences")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    def upsert_notification_preferences(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client().table("notification_preferences").upsert(payload).execute().data[0]

    def list_due_reminder_tasks(self) -> list[dict[str, Any]]:
        rows = (
            self.client()
            .rpc("due_reminder_tasks")
            .execute()
            .data
        )
        if not rows:
            return []
        task_ids = [str(row["task_id"]) for row in rows if row.get("task_id")]
        if not task_ids:
            return rows
        task_details = (
            self.client()
            .table("application_tasks")
            .select("id, opportunity_id, opportunities(public_code,title,provider,country,funding_type,deadline,application_url)")
            .in_("id", task_ids)
            .execute()
            .data
        )
        details_by_id = {str(row.get("id")): row for row in task_details}
        enriched = []
        for row in rows:
            detail = details_by_id.get(str(row.get("task_id"))) or {}
            opportunity = detail.get("opportunities") or {}
            enriched.append(
                {
                    **row,
                    "opportunity_id": opportunity.get("public_code") or detail.get("opportunity_id"),
                    "final_deadline": opportunity.get("deadline") or row.get("due_date"),
                    "opportunity": opportunity or None,
                }
            )
        return enriched

    def has_reminder_delivery(self, task_id: str, reminder_date: str, notification_email: str) -> bool:
        rows = (
            self.client()
            .table("reminder_deliveries")
            .select("id")
            .eq("task_id", task_id)
            .eq("reminder_date", reminder_date)
            .eq("notification_email", notification_email)
            .limit(1)
            .execute()
            .data
        )
        return bool(rows)

    def save_reminder_delivery(self, record: dict[str, Any]) -> dict[str, Any]:
        return (
            self.client()
            .table("reminder_deliveries")
            .upsert(record, on_conflict="task_id,reminder_date,notification_email")
            .execute()
            .data[0]
        )

    def create_search_job(self, user_id: str, query: str, profile: dict[str, Any]) -> dict[str, Any]:
        row = {
            "user_id": user_id,
            "query": query,
            "profile": profile,
            "status": "queued",
            "progress_message": "Queued",
            "current_stage": "queued",
            "stage_payload": {},
        }
        return self.client().table("search_jobs").insert(row).execute().data[0]

    def claim_next_search_job(self) -> dict[str, Any] | None:
        rows = (
            self.client()
            .table("search_jobs")
            .select("*")
            .eq("status", "queued")
            .order("created_at")
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return None
        job = rows[0]
        claimed = (
            self.client()
            .table("search_jobs")
            .update(
                {
                    "status": "running",
                    "progress_message": "Planning search queries",
                    "current_stage": "planning",
                    "attempt_count": int(job.get("attempt_count") or 0) + 1,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", job["id"])
            .eq("status", "queued")
            .execute()
            .data
        )
        return claimed[0] if claimed else None

    def claim_search_job_by_id(self, job_id: str) -> dict[str, Any] | None:
        existing = self.get_search_job_by_id(job_id) or {}
        claimed = (
            self.client()
            .table("search_jobs")
            .update(
                {
                    "status": "running",
                    "progress_message": "Planning search queries",
                    "current_stage": "planning",
                    "attempt_count": int(existing.get("attempt_count") or 0) + 1,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", job_id)
            .eq("status", "queued")
            .execute()
            .data
        )
        return claimed[0] if claimed else None

    def get_search_job(self, user_id: str, job_id: str) -> dict[str, Any] | None:
        rows = (
            self.client()
            .table("search_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    def get_search_job_by_id(self, job_id: str) -> dict[str, Any] | None:
        rows = (
            self.client()
            .table("search_jobs")
            .select("*")
            .eq("id", job_id)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None

    def list_search_jobs(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return (
            self.client()
            .table("search_jobs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    def list_queued_search_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        return (
            self.client()
            .table("search_jobs")
            .select("*")
            .eq("status", "queued")
            .order("created_at")
            .limit(limit)
            .execute()
            .data
        )

    def list_running_search_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        return (
            self.client()
            .table("search_jobs")
            .select("*")
            .eq("status", "running")
            .order("updated_at")
            .limit(limit)
            .execute()
            .data
        )

    def update_search_job(self, job_id: str, **updates: Any) -> dict[str, Any]:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self.client().table("search_jobs").update(updates).eq("id", job_id).execute().data[0]

    def update_search_stage(
        self,
        job_id: str,
        *,
        current_stage: str,
        progress_message: str,
        stage_payload: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {
            "current_stage": current_stage,
            "progress_message": progress_message,
        }
        if stage_payload is not None:
            updates["stage_payload"] = stage_payload
        if result is not None:
            updates["result"] = result
        return self.update_search_job(job_id, **updates)

    def fail_search_job(self, job_id: str, error: str, progress_message: str = "Search failed") -> dict[str, Any]:
        return self.update_search_job(
            job_id,
            status="failed",
            current_stage="failed",
            progress_message=progress_message,
            error=error,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    def cancel_search_job(self, user_id: str, job_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        rows = (
            self.client()
            .table("search_jobs")
            .update(
                {
                    "status": "cancelled",
                    "progress_message": "Search cancelled",
                    "error": "Cancelled by user",
                    "completed_at": now,
                    "cancelled_at": now,
                    "current_stage": "cancelled",
                    "updated_at": now,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .in_("status", ["queued", "running"])
            .execute()
            .data
        )
        if not rows:
            raise ValueError("Search job is not cancellable or was not found.")
        return rows[0]

    def retry_search_job(self, user_id: str, job_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        rows = (
            self.client()
            .table("search_jobs")
            .update(
                {
                    "status": "queued",
                    "progress_message": "Queued for retry",
                    "error": None,
                    "completed_at": None,
                    "cancelled_at": None,
                    "current_stage": "queued",
                    "updated_at": now,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .in_("status", ["failed", "cancelled"])
            .execute()
            .data
        )
        if not rows:
            raise ValueError("Search job is not retryable or was not found.")
        return rows[0]

    def delete_search_job(self, user_id: str, job_id: str) -> dict[str, Any]:
        rows = (
            self.client()
            .table("search_jobs")
            .delete()
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        if not rows:
            raise ValueError("Search job was not found.")
        return {"id": job_id, "deleted": True}

    def log_api_call(self, record: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self.client().table("api_call_logs").insert(record).execute().data[0]
        except Exception:
            return None

    def list_api_call_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return (
            self.client()
            .table("api_call_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    def admin_health_summary(self) -> dict[str, Any]:
        recent_logs = self.list_api_call_logs(limit=100)
        recent_jobs = (
            self.client()
            .table("search_jobs")
            .select("id,status,progress_message,error,created_at,completed_at")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )
        provider_stats: dict[str, dict[str, Any]] = {}
        for log in recent_logs:
            provider = log.get("provider") or "unknown"
            stats = provider_stats.setdefault(provider, {"calls": 0, "failures": 0, "avg_latency_ms": 0})
            stats["calls"] += 1
            if not log.get("success"):
                stats["failures"] += 1
            latency = log.get("latency_ms")
            if latency is not None:
                stats["avg_latency_ms"] += latency
        for stats in provider_stats.values():
            if stats["calls"]:
                stats["avg_latency_ms"] = round(stats["avg_latency_ms"] / stats["calls"])
        return {"providers": provider_stats, "recent_jobs": recent_jobs, "recent_api_calls": recent_logs[:20]}
