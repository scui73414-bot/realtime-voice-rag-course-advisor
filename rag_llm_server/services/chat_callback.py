import secrets

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from config import settings
from services.llm_service import llm_service
from services.rag_service import rag_service


def _verify_callback_authorization(request: Request) -> None:
    """Accept only the Bearer token configured for the RTC CustomLLM callback."""
    expected_token = settings.CALLBACK_AUTH_TOKEN
    if not expected_token:
        raise HTTPException(status_code=503, detail="RTC 回调鉴权尚未配置")

    received_header = request.headers.get("authorization", "")
    expected_header = f"Bearer {expected_token}"
    if not secrets.compare_digest(received_header, expected_header):
        raise HTTPException(
            status_code=401,
            detail="无效的 RTC 回调凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def build_chat_callback_response(request: Request) -> StreamingResponse:
    """Validate an RTC CustomLLM request and return OpenAI-compatible SSE."""
    _verify_callback_authorization(request)

    try:
        data = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from exc

    messages = data.get("messages", [])
    if not messages or messages[-1].get("role") != "user":
        raise HTTPException(status_code=400, detail="最后一条消息必须来自用户")

    async def generate_sse():
        question = messages[-1].get("content", "")
        rag_content = await rag_service.retrieve(question)
        for chunk in llm_service.chat_stream(messages, rag_content):
            if chunk:
                yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
