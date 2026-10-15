from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import jwt as pyjwt
from app.redis import shared_redis
import json
import httpx


load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")

bearer_scheme = HTTPBearer()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = creds.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    

    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:                    # ← pehle check
        raise credentials_exception

    # Redis cache check
    cached = await shared_redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    # Cache miss — auth service ko call karo
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AUTH_SERVICE_URL}/internal/verify-user",
            json={"user_id": user_id},
            headers={"X-Internal-Secret": INTERNAL_SECRET},
        )

    if response.status_code != 200:
        raise credentials_exception

    return response.json()