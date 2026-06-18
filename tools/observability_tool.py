import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import Settings, get_settings


class ApiCallLogger:
    def __init__(self) -> None:
        self._repository = None

    def log(
        self,
        *,
        provider: str,
        endpoint: str,
        model: str | None,
        status_code: int | None,
        latency_ms: int,
        success: bool,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            from tools.supabase_tool import SupabaseRepository

            if self._repository is None:
                self._repository = SupabaseRepository()
            self._repository.log_api_call(
                {
                    "provider": provider,
                    "endpoint": endpoint,
                    "model": model,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "success": success,
                    "error_message": error_message,
                    "metadata": metadata or {},
                }
            )
        except Exception:
            return


class ModelRateLimiter:
    def __init__(self) -> None:
        self._settings: Settings | None = None
        self._semaphore: threading.Semaphore | None = None
        self._limit = 0

    def _current(self) -> threading.Semaphore:
        settings = get_settings()
        limit = max(settings.max_parallel_model_calls, 1)
        if self._semaphore is None or self._settings is not settings or self._limit != limit:
            self._settings = settings
            self._limit = limit
            self._semaphore = threading.Semaphore(limit)
        return self._semaphore

    @contextmanager
    def slot(self) -> Iterator[None]:
        semaphore = self._current()
        semaphore.acquire()
        try:
            yield
        finally:
            semaphore.release()


api_call_logger = ApiCallLogger()
model_rate_limiter = ModelRateLimiter()


@contextmanager
def timed_api_call(
    *,
    provider: str,
    endpoint: str,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    state: dict[str, Any] = {"status_code": None, "success": False, "error_message": None}
    started = time.perf_counter()
    try:
        yield state
    except Exception as exc:
        state["error_message"] = str(exc)
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000)
        api_call_logger.log(
            provider=provider,
            endpoint=endpoint,
            model=model,
            status_code=state.get("status_code"),
            latency_ms=latency_ms,
            success=bool(state.get("success")),
            error_message=state.get("error_message"),
            metadata=metadata,
        )
