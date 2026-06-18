from tools.supabase_tool import SupabaseRepository


class FakeSettings:
    supabase_enabled = True


class FakeExecute:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        self.calls = []
        self._filters: dict[str, str] = {}

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, field, value):
        self.calls.append(("eq", field, value))
        self._filters[field] = value
        return self

    def limit(self, *args, **kwargs):
        self.calls.append(("limit", args, kwargs))
        return self

    def upsert(self, payload, **kwargs):
        self.calls.append(("upsert", payload, kwargs))
        return self

    def execute(self):
        self.calls.append(("execute",))
        if self.table_name != "student_profiles":
            return FakeExecute([])
        if self._filters.get("user_id") == "user-1":
            return FakeExecute([{"user_id": "user-1", "compass_user_id": "cu_3", "country": "Pakistan"}])
        if self._filters.get("compass_user_id"):
            return FakeExecute([])
        if any(call[0] == "upsert" for call in self.calls):
            payload = next(call[1] for call in self.calls if call[0] == "upsert")
            return FakeExecute([payload])
        return FakeExecute([])


class FakeClient:
    def table(self, name: str) -> FakeQuery:
        return FakeQuery(name)


def test_ensure_compass_user_id_returns_existing() -> None:
    repository = SupabaseRepository(FakeSettings())
    repository._client = FakeClient()
    assert repository.ensure_compass_user_id("user-1") == "cu_3"


def test_allocate_compass_user_id_starts_at_one_when_empty() -> None:
    repository = SupabaseRepository(FakeSettings())
    repository._client = FakeClient()
    assert repository.allocate_compass_user_id() == "cu_1"
