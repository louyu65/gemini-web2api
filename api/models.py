"""
OpenAI-compatible request/response models for the Gemini API wrapper.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str | list[dict]  # str or list of {type: text/image_url}


class ChatCompletionRequest(BaseModel):
    model: str = "gemini"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None  # ignored for now
    max_tokens: int | None = None  # ignored for now


class Choice(BaseModel):
    index: int = 0
    message: dict[str, Any]
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: dict[str, int] = Field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


class StreamChoice(BaseModel):
    index: int = 0
    delta: dict[str, str | None]
    finish_reason: str | None = None


class ChatCompletionStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]


class ImageGenerationRequest(BaseModel):
    model: str = "gemini"
    prompt: str
    n: int = 1
    size: str = "1024x1024"  # ignored for now
    response_format: Literal["url", "b64_json"] = "b64_json"


class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]


class ImageDownloadRequest(BaseModel):
    url: str


class RefreshCookieRequest(BaseModel):
    cookies: dict[str, str]


class RefreshCookieResponse(BaseModel):
    success: bool
    account_status: str
    description: str
    message: str
