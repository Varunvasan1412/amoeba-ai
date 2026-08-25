import os
import logging
from typing import Optional
from fastapi import Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jose import jwt, JWTError
from app.core.config import settings
from app.models.client_config import ClientConfig
from sqlalchemy import select
from app.core.database import async_session

logger = logging.getLogger("rate_limit")

def tenant_identifier(request: Request) -> str:
    """
    Identifies the requester for rate limiting.
    Priority:
    1. API Key (X-API-Key header)
    2. User ID (from JWT sub)
    3. Client ID (from JWT claims)
    4. Remote IP (Fallback)
    """
    # 1. API Key (Header or Query)
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if api_key:
        return f"apikey:{api_key}"

    # 2. JWT Auth
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub")
            client_id = payload.get("client_id")
            
            if client_id and user_id:
                return f"tenant:{client_id}:user:{user_id}"
            if user_id:
                return f"user:{user_id}"
        except JWTError:
            pass

    # 3. Fallback to IP
    return get_remote_address(request)

# Singleton Storage Configuration
def get_storage_uri():
    if not settings.RATE_LIMIT_ENABLED:
        return "memory://"
    
    if settings.REDIS_URL:
        import redis
        try:
            # Parse rediss:// or redis://
            from urllib.parse import urlparse
            url = urlparse(settings.REDIS_URL)
            r = redis.Redis(host=url.hostname, port=url.port or 6379, db=0, socket_connect_timeout=1)
            r.ping()
            logger.info("✅ Rate Limiter connected to Redis.")
            return settings.REDIS_URL
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable for Rate Limiting ({e}). Falling back to memory://")
            return "memory://"
    return "memory://"

storage_uri = get_storage_uri()

limiter = Limiter(
    key_func=tenant_identifier,
    storage_uri=storage_uri,
    enabled=settings.RATE_LIMIT_ENABLED,
    strategy="fixed-window",
    default_limits=[settings.RATE_LIMIT_GLOBAL]
)

from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter
from limits import parse

# Initialize Storage & Strategy for manual checks
storage = storage_from_string(storage_uri)
strategy = FixedWindowRateLimiter(storage)

def check_chat(client_id: int) -> bool:
    """Manual check for WebSockets / Services using Chat quota"""
    if not settings.RATE_LIMIT_ENABLED:
        return True
    
    try:
        limit = parse(settings.RATE_LIMIT_CHAT)
        # Key: tenant:{id}:chat
        # strategy.hit returns True if request is allowed, False if rejected
        return strategy.hit(limit, f"tenant:{client_id}:chat")
    except Exception as e:
        logger.warning(f"Rate limit check_chat failed (Redis down?): {e}")
        return True # Fail open

def check_export(client_id: int) -> bool:
    """Manual check for Services using Export quota"""
    if not settings.RATE_LIMIT_ENABLED:
        return True
    
    try:
        limit = parse(settings.RATE_LIMIT_EXPORT)
        # Key: tenant:{id}:export
        return strategy.hit(limit, f"tenant:{client_id}:export")
    except Exception as e:
        logger.warning(f"Rate limit check_export failed (Redis down?): {e}")
        return True # Fail open

# Attach to limiter instance for compatibility
limiter.check_chat = check_chat
limiter.check_export = check_export

async def rate_limit_reason_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom 429 handler to return structured JSON and log the event.
    """
    from app.services.audit_service import log_audit
    
    # Extract metadata for logging
    client_id = None
    user_id = None
    
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = str(payload.get("sub"))
            client_id = payload.get("client_id")
        except:
            pass

    # Try to resolve client_id AND email from body if it's a login attempt
    email = "Unknown"
    if request.url.path == "/api/login/access-token":
        try:
            body = await request.json()
            company_code = body.get("company_code")
            email = body.get("username") or body.get("email") or "Unknown"
            if company_code:
                async with async_session() as session:
                    res = await session.execute(select(ClientConfig).where(ClientConfig.company_code == company_code))
                    client = res.scalar_one_or_none()
                    if client:
                        client_id = client.id
                        
            # Record in LoginAudit as well for the "Login Activity" UI
            from app.models.login_audit import LoginAudit
            async with async_session() as session:
                login_audit = LoginAudit(
                    email=email,
                    client_id=int(client_id) if client_id else None,
                    company_code=company_code,
                    ip_address=get_remote_address(request) or "0.0.0.0",
                    user_agent=request.headers.get("user-agent", "Unknown"),
                    status="FAILED",
                    failure_reason="Rate Limit Exceeded: Multiple failed attempts"
                )
                session.add(login_audit)
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to record login rate limit audit: {e}")

    try:
        log_audit(
            client_id=int(client_id) if client_id else None,
            action="RATE_LIMIT_TRIGGERED",
            details={
                "endpoint": request.url.path,
                "limit": str(exc.detail),
                "ip": get_remote_address(request),
                "user_id": user_id,
                "email": email
            }
        )
    except Exception as e:
        logger.warning(f"Failed to log rate limit event: {e}")

    from fastapi.responses import JSONResponse
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests",
            "message": "Multiple failed attempts. Please wait 60 seconds before trying again.",
            "retry_after_seconds": 60,
            "limit": str(exc.detail)
        },
        headers={"Retry-After": "60"}
    )
