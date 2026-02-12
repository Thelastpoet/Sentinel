from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, cast

from fastapi import Header, HTTPException, status
from jwt import InvalidTokenError, decode

OAUTH_TOKEN_REGISTRY_ENV = "SENTINEL_OAUTH_TOKENS_JSON"
OAUTH_JWT_SECRET_ENV = "SENTINEL_OAUTH_JWT_SECRET"
OAUTH_JWT_ALGORITHM_ENV = "SENTINEL_OAUTH_JWT_ALGORITHM"
OAUTH_JWT_AUDIENCE_ENV = "SENTINEL_OAUTH_JWT_AUDIENCE"
OAUTH_JWT_ISSUER_ENV = "SENTINEL_OAUTH_JWT_ISSUER"
OAUTH_ALLOW_STATIC_TOKENS_ENV = "SENTINEL_OAUTH_ALLOW_STATIC_TOKENS"

DEFAULT_TOKEN_REGISTRY: dict[str, dict[str, object]] = {
    "internal-dev-token": {
        "client_id": "internal-dev-client",
        "scopes": [
            "internal:queue:read",
            "admin:proposal:read",
            "admin:proposal:review",
            "admin:appeal:read",
            "admin:appeal:write",
            "admin:transparency:read",
            "admin:transparency:export",
            "admin:transparency:identifiers",
        ],
    }
}


@dataclass(frozen=True)
class OAuthPrincipal:
    token: str
    client_id: str
    scopes: frozenset[str]


def _normalize_scopes(value: object) -> frozenset[str]:
    if isinstance(value, str):
        scope_items = value.split()
    elif isinstance(value, list):
        scope_items = [str(item) for item in value]
    else:
        raise ValueError("scopes must be a list or a space-delimited string")

    normalized = {item.strip() for item in scope_items if item.strip()}
    if not normalized:
        raise ValueError("at least one OAuth scope is required")
    return frozenset(normalized)


def _load_registry_payload() -> dict[str, object]:
    raw = os.getenv(OAUTH_TOKEN_REGISTRY_ENV)
    if not raw:
        return dict(DEFAULT_TOKEN_REGISTRY)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{OAUTH_TOKEN_REGISTRY_ENV} must be a JSON object")
    return payload


def load_token_registry() -> dict[str, OAuthPrincipal]:
    payload = _load_registry_payload()
    registry: dict[str, OAuthPrincipal] = {}
    for token, principal_payload in payload.items():
        if not isinstance(token, str) or not token.strip():
            raise ValueError("OAuth token keys must be non-empty strings")
        if not isinstance(principal_payload, dict):
            raise ValueError("OAuth token payloads must be objects")
        client_id = str(principal_payload.get("client_id", "oauth-client")).strip()
        scopes = _normalize_scopes(principal_payload.get("scopes"))
        registry[token.strip()] = OAuthPrincipal(
            token=token.strip(),
            client_id=client_id or "oauth-client",
            scopes=scopes,
        )
    return registry


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _decode_jwt_principal(token: str) -> OAuthPrincipal:
    secret = os.getenv(OAUTH_JWT_SECRET_ENV, "").strip()
    if not secret:
        raise ValueError(f"{OAUTH_JWT_SECRET_ENV} is required for JWT mode")

    algorithm = os.getenv(OAUTH_JWT_ALGORITHM_ENV, "HS256").strip() or "HS256"
    audience = os.getenv(OAUTH_JWT_AUDIENCE_ENV, "").strip() or None
    issuer = os.getenv(OAUTH_JWT_ISSUER_ENV, "").strip() or None
    options = cast(Any, {"verify_aud": audience is not None})
    try:
        claims = decode(
            token,
            key=secret,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options=options,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client_id = str(claims.get("client_id") or claims.get("sub") or "oauth-client").strip()
    scopes_claim = claims.get("scopes", claims.get("scope"))
    try:
        scopes = _normalize_scopes(scopes_claim)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid bearer token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return OAuthPrincipal(
        token=token,
        client_id=client_id or "oauth-client",
        scopes=scopes,
    )


def authenticate_bearer_token(authorization: str | None) -> OAuthPrincipal:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    normalized_token = token.strip()
    jwt_secret = os.getenv(OAUTH_JWT_SECRET_ENV, "").strip()
    if jwt_secret:
        return _decode_jwt_principal(normalized_token)

    allow_static_tokens = _as_bool(
        os.getenv(OAUTH_ALLOW_STATIC_TOKENS_ENV),
        default=True,
    )
    if not allow_static_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        registry = load_token_registry()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth token registry misconfigured: {exc}",
        ) from exc

    principal = registry.get(normalized_token)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_oauth_scope(required_scope: str):
    def dependency(authorization: str | None = Header(default=None)) -> OAuthPrincipal:
        principal = authenticate_bearer_token(authorization)
        if required_scope not in principal.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing OAuth scope: {required_scope}",
            )
        return principal

    return dependency
