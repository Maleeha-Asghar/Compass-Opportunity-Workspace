from tools.supabase_tool import SupabaseRepository


class FakeSettings:
    supabase_enabled = True


class FakeExecute:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self) -> None:
        self.calls = []
        self._user_id: str | None = None
        self._compass_user_id: str | None = None

    def upsert(self, payload, **kwargs):
        self.calls.append(("upsert", payload, kwargs))
        return self

    def update(self, payload):
        self.calls.append(("update", payload))
        return self

    def delete(self):
        self.calls.append(("delete",))
        return self

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, field, value):
        self.calls.append(("eq", field, value))
        if field == "user_id":
            self._user_id = value
        if field == "compass_user_id":
            self._compass_user_id = value
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return self

    def limit(self, *args, **kwargs):
        self.calls.append(("limit", args, kwargs))
        return self

    def execute(self):
        self.calls.append(("execute",))
        if any(call[0] == "delete" for call in self.calls):
            return FakeExecute([{"id": "row-id"}])
        if self._user_id == "user-1" and any(call[0] == "eq" and call[1] == "user_id" for call in self.calls):
            upserts = [call[1] for call in self.calls if call[0] == "upsert"]
            if upserts:
                return FakeExecute([upserts[-1]])
            return FakeExecute([])
        if self._compass_user_id:
            return FakeExecute([])
        if any(call[0] == "upsert" for call in self.calls):
            payload = next(call[1] for call in reversed(self.calls) if call[0] == "upsert")
            return FakeExecute([payload])
        return FakeExecute([{"id": "row-id"}])


class FakeClient:
    def __init__(self) -> None:
        self.queries = {}

    def table(self, name: str) -> FakeQuery:
        if name not in self.queries:
            self.queries[name] = FakeQuery()
        return self.queries[name]


def test_save_profile_upserts_on_user_id():
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    saved = repository.save_profile("user-1", {"country": "Pakistan"})

    assert saved["country"] == "Pakistan"
    assert saved["compass_user_id"] == "cu_1"
    upsert_calls = [call for call in client.queries["student_profiles"].calls if call[0] == "upsert"]
    assert upsert_calls[-1][1] == {
        "user_id": "user-1",
        "compass_user_id": "cu_1",
        "country": "Pakistan",
    }


def test_save_opportunity_for_user_upserts_on_user_and_opportunity():
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    repository.save_opportunity_for_user("user-1", "a1b")

    assert client.queries["saved_opportunities"].calls[0] == (
        "upsert",
        {"user_id": "user-1", "opportunity_id": "row-id"},
        {"on_conflict": "user_id,opportunity_id"},
    )


def test_fail_search_job_marks_job_failed():
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    repository.fail_search_job("job-1", "Groq planning unavailable", progress_message="Search planning failed")

    update_calls = [call for call in client.queries["search_jobs"].calls if call[0] == "update"]
    assert update_calls
    payload = update_calls[-1][1]
    assert payload["status"] == "failed"
    assert payload["progress_message"] == "Search planning failed"
    assert payload["error"] == "Groq planning unavailable"
    assert "completed_at" in payload


def test_claim_search_job_by_id_promotes_matching_job():
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    job = repository.claim_search_job_by_id("job-1")

    assert job["id"] == "row-id"
    assert any(call[0] == "update" for call in client.queries["search_jobs"].calls)


def test_claim_next_search_job_promotes_queued_job():
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    job = repository.claim_next_search_job()

    assert job["id"] == "row-id"
    assert client.queries["search_jobs"].calls[0][0] == "select"
    assert any(call[0] == "update" for call in client.queries["search_jobs"].calls)


def test_delete_search_job_scopes_to_user():
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    result = repository.delete_search_job("user-1", "job-1")

    calls = client.queries["search_jobs"].calls
    assert result == {"id": "job-1", "deleted": True}
    assert ("delete",) in calls
    assert ("eq", "id", "job-1") in calls
    assert ("eq", "user_id", "user-1") in calls


def test_display_application_task_uses_short_ids():
    row = {
        "id": "12345678-abcd-4321-abcd-123456789abc",
        "opportunity_id": "99999999-abcd-4321-abcd-123456789abc",
        "title": "Draft statement",
        "opportunities": {"public_code": "wme4o3e2", "title": "EMAI"},
    }

    task = SupabaseRepository._display_application_task(row)

    assert task["id"] == "12345678"
    assert task["task_code"] == "12345678"
    assert task["internal_id"] == "12345678-abcd-4321-abcd-123456789abc"
    assert task["opportunity_id"] == "wme4o3e2"
    assert task["opportunity"]["title"] == "EMAI"
    assert task["email_status"]["sent"] is False
    assert task["email_status"]["status"] == "not_sent"


def test_display_application_task_includes_email_delivery_status():
    row = {
        "id": "abcdef12-abcd-4321-abcd-123456789abc",
        "title": "Prepare transcript",
        "opportunity_id": "99999999-abcd-4321-abcd-123456789abc",
    }

    task = SupabaseRepository._display_application_task(
        row,
        reminder_deliveries=[
            {
                "sent_at": "2026-06-18T08:30:00+00:00",
                "notification_email": "student@example.com",
                "reminder_date": "2026-06-18",
            }
        ],
    )

    assert task["email_status"]["sent"] is True
    assert task["email_status"]["status"] == "sent"
    assert task["email_status"]["sent_count"] == 1
    assert task["email_status"]["sent_at"] == "2026-06-18T08:30:00+00:00"
    assert task["email_status"]["notification_email"] == "student@example.com"
