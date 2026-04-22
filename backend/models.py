"""
Pydantic models for VKS AI Platform
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============ Chat Models (OpenAI Compatible) ============

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="qwen3:30b-a3b", description="Model to use")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    temperature: Optional[float] = Field(default=0.3, ge=0, le=2)
    top_p: Optional[float] = Field(default=0.8, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=32768)
    stream: Optional[bool] = Field(default=False)
    stop: Optional[List[str]] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: UsageInfo


# ============ API Key Models ============

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="API key name")
    rate_limit: Optional[int] = Field(default=30, description="Rate limit per minute")
    description: Optional[str] = Field(default="", max_length=500)


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: Optional[str] = None  # Only shown on creation
    key_preview: str  # e.g., "vks-xxxx...xxxx"
    created_at: str
    last_used: Optional[str] = None
    is_active: bool = True
    rate_limit: int = 30
    total_requests: int = 0
    description: str = ""


class APIKeyListResponse(BaseModel):
    keys: List[APIKeyResponse]
    total: int


# ============ Admin Models ============

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours


# ============ Usage Models ============

class UsageLogEntry(BaseModel):
    api_key_id: str
    api_key_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: int
    timestamp: str
    endpoint: str


class UsageStats(BaseModel):
    total_requests: int = 0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    avg_response_time_ms: float = 0
    requests_today: int = 0
    tokens_today: int = 0
    top_models: List[Dict[str, Any]] = []
    daily_stats: List[Dict[str, Any]] = []


# ============ Model Info ============

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "vks-local"
    name: str = ""
    size: str = ""
    quantization: str = ""
    parameters: str = ""


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# ============ Conversation Models ============

class ConversationCreate(BaseModel):
    title: Optional[str] = "Cuộc hội thoại mới"
    system_prompt: Optional[str] = ""


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    system_prompt: str = ""


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


# ============ General ============

class ErrorResponse(BaseModel):
    error: Dict[str, Any] = Field(
        ...,
        example={
            "message": "Invalid API key",
            "type": "authentication_error",
            "code": "invalid_api_key"
        }
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    ollama_connected: bool
    mongodb_connected: bool
    default_model: str
    uptime_seconds: float
