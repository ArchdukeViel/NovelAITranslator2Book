# Design: Authentication and Authorization

## Overview

Add a `User` model, a JWT auth service, role-based dependency injection, and update all owner endpoints to require authentication. Uses FastAPI's built-in OAuth2 support. One new DB table. No changes to existing business logic beyond adding `Depends(require_role("owner"))` to protected routes.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/db/models/user.py` | New — `User` SQLAlchemy model |
| `backend/src/novelai/api/auth/__init__.py` | New — auth package |
| `backend/src/novelai/api/auth/router.py` | New — `POST /api/auth/login` |
| `backend/src/novelai/api/auth/dependencies.py` | New — `get_current_user`, `require_role` |
| `backend/src/novelai/api/auth/schemas.py` | New — `LoginRequest`, `TokenResponse`, `TokenPayload` |
| `backend/src/novelai/api/routers/library.py` | Update — add `Depends(require_role("owner"))` |
| `backend/src/novelai/api/routers/operations.py` | Update — add `Depends(require_role("owner"))` |
| `backend/src/novelai/api/routers/admin_glossary.py` | Update — add `Depends(require_role("owner"))` |
| `backend/src/novelai/main.py` | Update — register auth router, add OAuth2 scheme |
| `Alembic migration` | New — `users` table |
| `backend/src/novelai/cli/commands.py` | Update — add `create-user` command |

### Files Not Touched

- Public API routers — no auth added
- Translation pipeline — no change
- Storage layer — no change
- Source adapters — no change
- Frontend — no change

## Component Design

### 1. `User` Model (`db/models/user.py`)

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from novelai.db.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="owner")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### 2. Auth Dependencies (`api/auth/dependencies.py`)

```python
from datetime import datetime, timedelta, timezone
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from pydantic import BaseModel

from novelai.db.engine import get_db_session
from novelai.db.models.user import User

JWT_SECRET = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class TokenPayload(BaseModel):
    sub: int
    username: str
    role: str
    exp: int


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = TokenPayload(
        sub=user.id,
        username=user.username,
        role=user.role,
        exp=int(expire.timestamp()),
    )
    return jwt.encode(payload.model_dump(), JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**data)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    payload = decode_token(token)
    user = db.query(User).filter_by(id=payload.sub).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user


def require_role(role: str):
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker
```

### 3. Login Endpoint (`api/auth/router.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from novelai.api.auth.dependencies import verify_password, create_access_token
from novelai.api.auth.schemas import LoginRequest, TokenResponse
from novelai.db.engine import get_db_session
from novelai.db.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db_session)):
    user = db.query(User).filter_by(username=body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )
    return TokenResponse(
        access_token=create_access_token(user),
        token_type="bearer",
    )


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
```

### 4. Endpoint Protection Pattern

Each protected endpoint adds:

```python
@router.post("/{novel_id}/scrape")
async def scrape_novel(
    novel_id: str,
    _owner: User = Depends(require_role("owner")),
    ...
):
```

### 5. Startup Validation (`main.py`)

```python
import os

if not os.environ.get("JWT_SECRET_KEY"):
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required for authentication. "
        "Set it to a random string (e.g. openssl rand -hex 32)."
    )
```

### 6. Rate Limiting on Login

Use a simple in-memory counter (dictionary with IP as key, reset after 60s):

```python
from collections import defaultdict
import time

_login_attempts: dict[str, list[float]] = defaultdict(list)

def check_login_rate_limit(ip: str) -> None:
    now = time.time()
    window = now - 60
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > window]
    if len(_login_attempts[ip]) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    _login_attempts[ip].append(now)
```

## Migration and Backward Compatibility

- Public endpoints remain unauthenticated (no change).
- Existing owner endpoints remain at the same paths; only the dependency chain adds auth.
- The first user must be created via CLI before owner endpoints can be used.
- Existing test fixtures that call owner endpoints must be updated to include an auth header.

## Acceptance Criteria

1. `POST /api/auth/login` with valid credentials returns a JWT access token.
2. `POST /api/auth/login` with invalid credentials returns HTTP 401 with `"Invalid credentials"`.
3. An unauthenticated call to `POST /{novel_id}/scrape` returns HTTP 401.
4. An authenticated non-owner call to owner endpoints returns HTTP 403.
5. The Swagger UI shows a lock icon on protected endpoints and an "Authorize" button.
6. The application refuses to start if `JWT_SECRET_KEY` is not set.
7. Rate limiting blocks login after 5 failed attempts within 1 minute.
