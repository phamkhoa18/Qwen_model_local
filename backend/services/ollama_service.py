"""
Ollama service - handles all communication with Ollama LLM server
"""
import httpx
import json
import time
import uuid
from typing import AsyncGenerator, Optional, List, Dict
from datetime import datetime, timezone
from backend.config import settings


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5 min for generation

    async def is_connected(self) -> bool:
        """Check if Ollama is running"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict]:
        """List all available models"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
        except Exception as e:
            print(f"Error listing models: {e}")
        return []

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        top_p: float = 0.8,
        max_tokens: int = 4096,
        stop: Optional[List[str]] = None
    ) -> Dict:
        """Non-streaming chat completion"""
        start_time = time.time()
        
        payload = {
            "model": model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            }
        }
        
        if stop:
            payload["options"]["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                
                if response.status_code != 200:
                    raise Exception(f"Ollama error: {response.status_code} - {response.text}")
                
                data = response.json()
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # Build OpenAI-compatible response
                completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": data.get("message", {}).get("content", "")
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    },
                    "response_time_ms": elapsed_ms
                }
                
        except httpx.ConnectError:
            raise Exception("Cannot connect to Ollama. Make sure Ollama is running (ollama serve)")
        except Exception as e:
            raise Exception(f"Chat completion error: {str(e)}")

    async def chat_completion_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        top_p: float = 0.8,
        max_tokens: int = 4096,
        stop: Optional[List[str]] = None
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion - yields SSE formatted chunks"""
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        
        payload = {
            "model": model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            }
        }
        
        if stop:
            payload["options"]["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            done = data.get("done", False)
                            
                            if content:
                                chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": content},
                                            "finish_reason": None
                                        }
                                    ]
                                }
                                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            
                            if done:
                                # Final chunk
                                final_chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {},
                                            "finish_reason": "stop"
                                        }
                                    ],
                                    "usage": {
                                        "prompt_tokens": data.get("prompt_eval_count", 0),
                                        "completion_tokens": data.get("eval_count", 0),
                                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                                    }
                                }
                                yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
                                yield "data: [DONE]\n\n"
                                
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.ConnectError:
            error_chunk = {
                "error": {
                    "message": "Cannot connect to Ollama. Make sure Ollama is running.",
                    "type": "server_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
        except Exception as e:
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

    async def get_model_info(self, model: str) -> Optional[Dict]:
        """Get detailed info about a specific model"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model}
                )
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return None

    async def pull_model(self, model: str) -> AsyncGenerator[str, None]:
        """Pull/download a model - streams progress"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0)) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/pull",
                    json={"name": model, "stream": True}
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            yield line + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"


ollama_service = OllamaService()
