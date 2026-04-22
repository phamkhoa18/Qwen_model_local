"""
Authentication and rate limiting middleware
"""
import hashlib
import time
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from backend.database import db
from backend.config import settings

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
x_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(key.encode()).hexdigest()


async def get_api_key_from_request(request: Request) -> dict:
    """Extract and validate API key from request headers"""
    api_key = None
    
    # Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
    
    # Check X-API-Key header
    if not api_key:
        api_key = request.headers.get("X-API-Key", "")
    
    # Check query parameter
    if not api_key:
        api_key = request.query_params.get("api_key", "")
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing API key. Include it in Authorization header as 'Bearer vks-xxx' or X-API-Key header.",
                    "type": "authentication_error",
                    "code": "missing_api_key"
                }
            }
        )
    
    # Validate key
    key_hash = hash_api_key(api_key)
    key_doc = await db.api_keys().find_one({"key_hash": key_hash, "is_active": True})
    
    if not key_doc:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid or revoked API key.",
                    "type": "authentication_error",
                    "code": "invalid_api_key"
                }
            }
        )
    
    # Check rate limit
    await check_rate_limit(str(key_doc["_id"]), key_doc.get("rate_limit", settings.RATE_LIMIT_PER_MINUTE))
    
    # Update last_used
    await db.api_keys().update_one(
        {"_id": key_doc["_id"]},
        {
            "$set": {"last_used": datetime.now(timezone.utc).isoformat()},
            "$inc": {"total_requests": 1}
        }
    )
    
    return key_doc


async def check_rate_limit(key_id: str, limit: int):
    """Check rate limit for API key using sliding window"""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=1)
    
    # Count requests in the last minute
    count = await db.usage_logs().count_documents({
        "api_key_id": key_id,
        "timestamp": {"$gte": window_start.isoformat()}
    })
    
    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"Rate limit exceeded. Maximum {limit} requests per minute.",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded"
                }
            }
        )


async def validate_admin_token(request: Request) -> bool:
    """Validate admin JWT token"""
    import jwt
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": {"message": "Missing admin token", "type": "auth_error"}})
    
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail={"error": {"message": "Not an admin", "type": "auth_error"}})
        return True
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"error": {"message": "Token expired", "type": "auth_error"}})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid token", "type": "auth_error"}})
