from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings


bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    raw: dict[str, Any]


class SupabaseAuth:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    def client(self) -> Any:
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise RuntimeError("supabase is required for auth validation.") from exc
            url, _ = self.settings.require_supabase()
            if not self.settings.supabase_anon_key:
                raise RuntimeError("SUPABASE_ANON_KEY is required for auth validation.")
            self._client = create_client(url, self.settings.supabase_anon_key)
        return self._client

    def verify(self, token: str) -> CurrentUser:
        try:
            result = self.client().auth.get_user(token)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Supabase JWT.",
            ) from exc
        user = result.user
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase JWT.")
        return CurrentUser(id=str(user.id), email=getattr(user, "email", None), raw=user.model_dump())


auth = SupabaseAuth()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> CurrentUser:
    return auth.verify(credentials.credentials)
