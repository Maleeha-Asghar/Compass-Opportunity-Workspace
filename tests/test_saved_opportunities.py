from tools.supabase_tool import SupabaseRepository


class FakeSettings:
    supabase_enabled = True


class FakeExecute:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table_name: str, client: "FakeClient") -> None:
        self.table_name = table_name
        self.client = client
        self.calls = []
        self.filters: dict[str, object] = {}

    def upsert(self, payload, **kwargs):
        self.calls.append(("upsert", payload, kwargs))
        return self

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, *args, **kwargs):
        self.calls.append(("eq", args, kwargs))
        if len(args) >= 2:
            self.filters[str(args[0])] = args[1]
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return self

    def limit(self, *args, **kwargs):
        self.calls.append(("limit", args, kwargs))
        return self

    def insert(self, payload):
        self.calls.append(("insert", payload))
        return self

    def execute(self):
        self.calls.append(("execute",))
        if self.table_name == "saved_opportunities" and any(call[0] == "select" for call in self.calls):
            return FakeExecute(
                [
                    {
                        "id": "saved-1",
                        "created_at": "2026-06-12T00:00:00+00:00",
                        "opportunity_id": "opp-uuid",
                        "opportunities": {
                            "id": "opp-uuid",
                            "public_code": "a1b",
                            "title": "Quantum internship",
                            "provider": "CERN",
                        },
                    }
                ]
            )
        if self.table_name == "opportunities":
            if any(call[0] == "insert" for call in self.calls):
                return FakeExecute([{"id": "new-uuid", "public_code": "x7z", "title": "Quantum internship"}])
            if any(call[0] == "select" for call in self.calls):
                if self.filters.get("public_code") and self.filters["public_code"] != "a1b":
                    return FakeExecute([])
                return FakeExecute([{"id": "opp-uuid", "public_code": "a1b", "title": "Quantum internship"}])
            return FakeExecute([{"id": "opp-uuid", "public_code": "a1b", "title": "Quantum internship"}])
        if self.table_name == "user_opportunity_matches":
            if any(call[0] == "select" for call in self.calls):
                return FakeExecute(
                    [
                        {
                            "opportunity_id": "opp-uuid",
                            "eligibility_result": {"eligible": True, "score": 0.91},
                            "priority": "high",
                            "priority_score": 0.91,
                            "notes": "Strong fit",
                        }
                    ]
                )
            if any(call[0] == "upsert" for call in self.calls):
                payload = next(call[1] for call in reversed(self.calls) if call[0] == "upsert")
                return FakeExecute([payload])
        return FakeExecute([{"id": "saved-1", "created_at": "2026-06-12T00:00:00+00:00"}])


class FakeClient:
    def __init__(self) -> None:
        self.queries: dict[str, FakeQuery] = {}

    def table(self, name: str) -> FakeQuery:
        if name not in self.queries:
            self.queries[name] = FakeQuery(name, self)
        return self.queries[name]


def test_list_saved_opportunities_scoped_to_user() -> None:
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    rows = repository.list_saved_opportunities("user-1")

    assert len(rows) == 1
    assert rows[0]["id"] == "a1b"
    assert rows[0]["saved_id"] == "saved-1"
    assert rows[0]["priority"] == "high"
    assert rows[0]["eligibility_result"]["score"] == 0.91
    saved_query = client.queries["saved_opportunities"]
    assert any(call[0] == "eq" and call[1] == ("user_id", "user-1") for call in saved_query.calls)


def test_unsave_opportunity_for_user_deletes_link() -> None:
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    class DeleteQuery(FakeQuery):
        def delete(self):
            self.calls.append(("delete",))
            return self

    client.queries["saved_opportunities"] = DeleteQuery("saved_opportunities", client)
    client.queries["saved_opportunities"].execute = lambda: FakeExecute([{"opportunity_id": "a1b"}])

    result = repository.unsave_opportunity_for_user("user-1", "a1b")

    assert result["opportunity_id"] == "a1b"
    assert result["removed"] is True
    assert any(call[0] == "delete" for call in client.queries["saved_opportunities"].calls)


def test_save_opportunity_for_user_record_creates_and_links() -> None:
    client = FakeClient()
    repository = SupabaseRepository(FakeSettings())
    repository._client = client

    result = repository.save_opportunity_for_user_record(
        "user-1",
        opportunity={
            "title": "Quantum internship",
            "application_url": "https://example.com/apply",
            "opportunity_type": "Research internship",
            "eligibility_result": {"eligible": True, "score": 0.88},
            "priority": "high",
            "priority_score": 0.88,
        },
    )

    assert result["opportunity_id"] == "x7z"
    assert result["saved_id"] == "saved-1"
    assert result["opportunity"]["title"] == "Quantum internship"
    opportunity_insert = next(call for call in client.queries["opportunities"].calls if call[0] == "insert")
    assert opportunity_insert[1]["opportunity_type"] == "internship"
    assert "eligibility_result" not in opportunity_insert[1]
    assert "priority" not in opportunity_insert[1]
    assert "priority_score" not in opportunity_insert[1]
    match_upsert = next(call for call in client.queries["user_opportunity_matches"].calls if call[0] == "upsert")
    assert match_upsert[1]["eligibility_result"]["score"] == 0.88
    assert match_upsert[1]["priority"] == "high"
