"""
Chat completion routes - OpenAI compatible API
"""
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from backend.models import ChatCompletionRequest, ChatCompletionResponse, ErrorResponse
from backend.middleware import get_api_key_from_request
from backend.services.ollama_service import ollama_service
from backend.database import db

router = APIRouter()


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion endpoint.
    Supports both streaming and non-streaming responses.
    """
    # Authenticate
    api_key_doc = await get_api_key_from_request(request)
    
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    
    if body.stream:
        # Streaming response
        async def stream_and_log():
            start_time = time.time()
            total_content = ""
            prompt_tokens = 0
            completion_tokens = 0
            
            async for chunk in ollama_service.chat_completion_stream(
                model=body.model,
                messages=messages,
                temperature=body.temperature,
                top_p=body.top_p,
                max_tokens=body.max_tokens,
                stop=body.stop
            ):
                # Try to extract usage from final chunk
                if '"finish_reason": "stop"' in chunk and '"usage"' in chunk:
                    import json
                    try:
                        data_str = chunk.replace("data: ", "").strip()
                        data = json.loads(data_str)
                        usage = data.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                    except Exception:
                        pass
                
                yield chunk
            
            # Log usage after stream completes
            elapsed_ms = int((time.time() - start_time) * 1000)
            await _log_usage(
                api_key_doc=api_key_doc,
                model=body.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time_ms=elapsed_ms,
                endpoint="/v1/chat/completions"
            )
        
        return StreamingResponse(
            stream_and_log(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming response
        try:
            result = await ollama_service.chat_completion(
                model=body.model,
                messages=messages,
                temperature=body.temperature,
                top_p=body.top_p,
                max_tokens=body.max_tokens,
                stop=body.stop
            )
            
            # Log usage
            await _log_usage(
                api_key_doc=api_key_doc,
                model=body.model,
                prompt_tokens=result["usage"]["prompt_tokens"],
                completion_tokens=result["usage"]["completion_tokens"],
                response_time_ms=result.get("response_time_ms", 0),
                endpoint="/v1/chat/completions"
            )
            
            # Remove internal field
            result.pop("response_time_ms", None)
            
            return result
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "message": str(e),
                        "type": "server_error",
                        "code": "ollama_error"
                    }
                }
            )


async def _log_usage(
    api_key_doc: dict,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    response_time_ms: int,
    endpoint: str
):
    """Log API usage to MongoDB"""
    try:
        log_entry = {
            "api_key_id": str(api_key_doc["_id"]),
            "api_key_name": api_key_doc.get("name", "unknown"),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "response_time_ms": response_time_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint
        }
        await db.usage_logs().insert_one(log_entry)
    except Exception as e:
        print(f"Error logging usage: {e}")
