"""
Admin routes - login, usage stats, system info
"""
import jwt
import time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException
from backend.models import AdminLoginRequest, AdminLoginResponse, UsageStats
from backend.middleware import validate_admin_token
from backend.database import db
from backend.config import settings
from backend.services.ollama_service import ollama_service

router = APIRouter()

# Track server start time
_start_time = time.time()


@router.post("/api/admin/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest):
    """Admin login - returns JWT token"""
    if body.username != settings.ADMIN_USERNAME or body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "Invalid username or password", "type": "auth_error"}}
        )
    
    # Generate JWT
    payload = {
        "sub": body.username,
        "role": "admin",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    
    return AdminLoginResponse(access_token=token)


@router.get("/api/admin/usage")
async def get_usage_stats(request: Request):
    """Get usage statistics (requires admin token)"""
    await validate_admin_token(request)
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    # Total stats
    pipeline_total = [
        {
            "$group": {
                "_id": None,
                "total_requests": {"$sum": 1},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                "total_completion_tokens": {"$sum": "$completion_tokens"},
                "avg_response_time_ms": {"$avg": "$response_time_ms"}
            }
        }
    ]
    
    total_stats = await db.usage_logs().aggregate(pipeline_total).to_list(1)
    total = total_stats[0] if total_stats else {}
    
    # Today stats
    pipeline_today = [
        {"$match": {"timestamp": {"$gte": today_start}}},
        {
            "$group": {
                "_id": None,
                "requests_today": {"$sum": 1},
                "tokens_today": {"$sum": "$total_tokens"}
            }
        }
    ]
    
    today_stats = await db.usage_logs().aggregate(pipeline_today).to_list(1)
    today = today_stats[0] if today_stats else {}
    
    # Top models
    pipeline_models = [
        {
            "$group": {
                "_id": "$model",
                "count": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"}
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    top_models = await db.usage_logs().aggregate(pipeline_models).to_list(10)
    
    # Daily stats (last 30 days)
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    pipeline_daily = [
        {"$match": {"timestamp": {"$gte": thirty_days_ago}}},
        {
            "$group": {
                "_id": {"$substr": ["$timestamp", 0, 10]},
                "requests": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "avg_response_ms": {"$avg": "$response_time_ms"}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    daily_stats = await db.usage_logs().aggregate(pipeline_daily).to_list(30)
    
    # Per-key stats
    pipeline_keys = [
        {
            "$group": {
                "_id": "$api_key_name",
                "requests": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"}
            }
        },
        {"$sort": {"requests": -1}},
        {"$limit": 20}
    ]
    
    key_stats = await db.usage_logs().aggregate(pipeline_keys).to_list(20)
    
    return {
        "total_requests": total.get("total_requests", 0),
        "total_tokens": total.get("total_tokens", 0),
        "total_prompt_tokens": total.get("total_prompt_tokens", 0),
        "total_completion_tokens": total.get("total_completion_tokens", 0),
        "avg_response_time_ms": round(total.get("avg_response_time_ms", 0), 2),
        "requests_today": today.get("requests_today", 0),
        "tokens_today": today.get("tokens_today", 0),
        "top_models": [{"model": m["_id"], "count": m["count"], "tokens": m["tokens"]} for m in top_models],
        "daily_stats": [{"date": d["_id"], "requests": d["requests"], "tokens": d["tokens"], "avg_response_ms": round(d["avg_response_ms"], 2)} for d in daily_stats],
        "key_stats": [{"key_name": k["_id"], "requests": k["requests"], "tokens": k["tokens"]} for k in key_stats]
    }


@router.get("/api/admin/health")
async def health_check():
    """System health check"""
    ollama_ok = await ollama_service.is_connected()
    mongo_ok = await db.is_connected()
    
    return {
        "status": "ok" if (ollama_ok and mongo_ok) else "degraded",
        "version": settings.APP_VERSION,
        "ollama_connected": ollama_ok,
        "mongodb_connected": mongo_ok,
        "default_model": settings.DEFAULT_MODEL,
        "uptime_seconds": round(time.time() - _start_time, 2)
    }


@router.get("/api/admin/models")
async def list_models_admin(request: Request):
    """List all Ollama models with details (admin)"""
    await validate_admin_token(request)
    
    models = await ollama_service.list_models()
    
    return {
        "object": "list",
        "data": [
            {
                "id": m.get("name", ""),
                "object": "model",
                "created": 0,
                "owned_by": "local",
                "name": m.get("name", ""),
                "size": _format_size(m.get("size", 0)),
                "size_bytes": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
                "digest": m.get("digest", "")[:12],
                "details": m.get("details", {})
            }
            for m in models
        ]
    }


@router.get("/v1/models")
async def list_models():
    """OpenAI-compatible model listing (public)"""
    models = await ollama_service.list_models()
    
    return {
        "object": "list",
        "data": [
            {
                "id": m.get("name", ""),
                "object": "model",
                "created": 0,
                "owned_by": "vks-local"
            }
            for m in models
        ]
    }


def _format_size(size_bytes: int) -> str:
    """Format bytes to human readable"""
    if size_bytes == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"
