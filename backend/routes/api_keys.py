"""
API Key management routes
"""
import secrets
import hashlib
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException
from backend.models import APIKeyCreate, APIKeyResponse, APIKeyListResponse
from backend.middleware import validate_admin_token, hash_api_key
from backend.database import db
from backend.config import settings

router = APIRouter()


def generate_api_key() -> str:
    """Generate a new API key"""
    random_part = secrets.token_hex(settings.API_KEY_LENGTH // 2)
    return f"{settings.API_KEY_PREFIX}{random_part}"


def get_key_preview(key: str) -> str:
    """Get preview of API key (first 8 + last 4 chars)"""
    if len(key) <= 12:
        return key[:4] + "..." + key[-4:]
    return key[:8] + "..." + key[-4:]


@router.post("/api/keys", response_model=APIKeyResponse)
async def create_api_key(request: Request, body: APIKeyCreate):
    """Create a new API key (requires admin token)"""
    await validate_admin_token(request)
    
    # Generate key
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    
    # Store in database
    key_doc = {
        "name": body.name,
        "key_hash": key_hash,
        "key_preview": get_key_preview(raw_key),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
        "is_active": True,
        "rate_limit": body.rate_limit or settings.RATE_LIMIT_PER_MINUTE,
        "total_requests": 0,
        "description": body.description or ""
    }
    
    result = await db.api_keys().insert_one(key_doc)
    
    return APIKeyResponse(
        id=str(result.inserted_id),
        name=body.name,
        key=raw_key,  # Only shown once on creation!
        key_preview=get_key_preview(raw_key),
        created_at=key_doc["created_at"],
        is_active=True,
        rate_limit=key_doc["rate_limit"],
        total_requests=0,
        description=key_doc["description"]
    )


@router.get("/api/keys", response_model=APIKeyListResponse)
async def list_api_keys(request: Request):
    """List all API keys (requires admin token)"""
    await validate_admin_token(request)
    
    cursor = db.api_keys().find().sort("created_at", -1)
    keys = []
    
    async for key_doc in cursor:
        keys.append(APIKeyResponse(
            id=str(key_doc["_id"]),
            name=key_doc["name"],
            key=None,  # Never show full key in listing
            key_preview=key_doc["key_preview"],
            created_at=key_doc["created_at"],
            last_used=key_doc.get("last_used"),
            is_active=key_doc.get("is_active", True),
            rate_limit=key_doc.get("rate_limit", 30),
            total_requests=key_doc.get("total_requests", 0),
            description=key_doc.get("description", "")
        ))
    
    return APIKeyListResponse(keys=keys, total=len(keys))


@router.delete("/api/keys/{key_id}")
async def revoke_api_key(request: Request, key_id: str):
    """Revoke (deactivate) an API key"""
    await validate_admin_token(request)
    
    try:
        result = await db.api_keys().update_one(
            {"_id": ObjectId(key_id)},
            {"$set": {"is_active": False, "revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"error": {"message": "API key not found"}})
        
        return {"message": "API key revoked successfully", "id": key_id}
    except Exception as e:
        if "not found" in str(e).lower():
            raise
        raise HTTPException(status_code=400, detail={"error": {"message": f"Invalid key ID: {str(e)}"}})


@router.patch("/api/keys/{key_id}")
async def update_api_key(request: Request, key_id: str, body: APIKeyCreate):
    """Update API key settings"""
    await validate_admin_token(request)
    
    try:
        update_data = {}
        if body.name:
            update_data["name"] = body.name
        if body.rate_limit:
            update_data["rate_limit"] = body.rate_limit
        if body.description is not None:
            update_data["description"] = body.description
        
        result = await db.api_keys().update_one(
            {"_id": ObjectId(key_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail={"error": {"message": "API key not found"}})
        
        return {"message": "API key updated", "id": key_id}
    except Exception as e:
        if "not found" in str(e).lower():
            raise
        raise HTTPException(status_code=400, detail={"error": {"message": str(e)}})


@router.post("/api/keys/{key_id}/regenerate", response_model=APIKeyResponse)
async def regenerate_api_key(request: Request, key_id: str):
    """Regenerate an API key (creates new key, same settings)"""
    await validate_admin_token(request)
    
    try:
        # Get existing key
        key_doc = await db.api_keys().find_one({"_id": ObjectId(key_id)})
        if not key_doc:
            raise HTTPException(status_code=404, detail={"error": {"message": "API key not found"}})
        
        # Generate new key
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        
        # Update
        await db.api_keys().update_one(
            {"_id": ObjectId(key_id)},
            {
                "$set": {
                    "key_hash": key_hash,
                    "key_preview": get_key_preview(raw_key),
                    "regenerated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return APIKeyResponse(
            id=key_id,
            name=key_doc["name"],
            key=raw_key,  # Show new key once
            key_preview=get_key_preview(raw_key),
            created_at=key_doc["created_at"],
            is_active=True,
            rate_limit=key_doc.get("rate_limit", 30),
            total_requests=key_doc.get("total_requests", 0),
            description=key_doc.get("description", "")
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise
        raise HTTPException(status_code=400, detail={"error": {"message": str(e)}})
