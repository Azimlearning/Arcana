"""Authentication layer — FR-USR-01, NFR-SEC-01.

Provides a FastAPI dependency ``get_current_user()`` that resolves the caller
to a ``CurrentUser`` dataclass. Two modes:

1. **Firebase-backed** (``firebase_project_id`` set in Settings): verifies the
   Bearer token via Google's tokeninfo endpoint. No SDK required — one httpx
   call. Returns 401 on invalid/expired tokens.

2. **Dev stub** (``ENV=local`` and no ``firebase_project_id``): reads the
   ``X-Dev-User-Id`` header and treats its value as the user id. Falls back to
   the anonymous user ``anon``. Appropriate for local development only.

All guarded routes use ``Depends(get_current_user)``.  Routes that do NOT
require auth (e.g. health, static assets) remain unguarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.core.logging import get_logger
from api.core.settings import Settings, get_settings

logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

_GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"

_DEV_ANON_USER = "anon"


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str | None = None
    display_name: str | None = None
    # Populated when notebook scope is present in the token claims.
    default_notebook_id: str | None = None
    # Internal flag — never expose via API.
    _is_anon: bool = field(default=False, compare=False)

    @property
    def is_anonymous(self) -> bool:
        return self._is_anon


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CurrentUser:
    """FastAPI dependency — resolve and return the current authenticated user.

    Raises HTTP 401 if authentication fails in non-local environments.
    """
    if settings.firebase_project_id:
        return await _verify_firebase_token(credentials, settings)

    # Local dev: anonymous mode with optional X-Dev-User-Id header.
    if settings.env == "local":
        dev_uid = request.headers.get("X-Dev-User-Id", _DEV_ANON_USER)
        return CurrentUser(uid=dev_uid, _is_anon=(dev_uid == _DEV_ANON_USER))

    # Neither Firebase nor local — deny by default (secure-by-default).
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication not configured on this server.",
    )


async def _verify_firebase_token(
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                _GOOGLE_TOKENINFO,
                params={"id_token": token},
            )
    except httpx.HTTPError as exc:
        logger.warning("auth.tokeninfo_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unreachable.",
        ) from exc

    if resp.status_code != 200:
        logger.warning("auth.token_invalid", status=resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = resp.json()
    project_id = settings.firebase_project_id
    if claims.get("aud") != project_id:
        logger.warning(
            "auth.wrong_audience",
            got=claims.get("aud"),
            expected=project_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience mismatch.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        uid=str(claims.get("sub", "")),
        email=claims.get("email"),
        display_name=claims.get("name"),
    )
