"""Session verification for Better Auth-issued tokens.

The API is a resource server: it accepts nothing but a Better Auth session JWT,
verified against Better Auth's published JWKS. It holds no passwords and no
sessions of its own.
"""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from src.config import settings

_jwks = PyJWKClient(settings.auth_jwks_url, cache_keys=True, lifespan=300)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    if settings.enable_dev_auth:
        return CurrentUser(id=settings.dev_user_id, email="dev@local")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        signing_key = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA"],
            audience=settings.auth_audience,
            options={"verify_aud": settings.auth_audience != ""},
        )
    except jwt.PyJWTError as error:
        raise _unauthorized(f"Invalid session token: {error}") from error
    except Exception as error:
        raise _unauthorized(f"Could not verify session token: {error}") from error

    subject = claims.get("sub")
    if not subject:
        raise _unauthorized("Session token has no subject")

    return CurrentUser(id=subject, email=claims.get("email"))


CurrentUserDep = Annotated[CurrentUser, Depends(current_user)]
