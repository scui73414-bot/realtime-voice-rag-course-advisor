import json
import time
from pathlib import Path
from typing import List

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import settings
from services.chat_callback import build_chat_callback_response
from services.llm_service import llm_service
from services.rag_service import rag_service
from services.token_build import AccessToken, PRIVILEGES
from services.utils import Signer

is_production = settings.APP_ENV == "production"
app = FastAPI(
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_debug_mode() -> None:
    """Keep cost-bearing debug endpoints out of the public deployment."""
    if settings.APP_ENV == "production":
        raise HTTPException(status_code=404, detail="Not Found")


@app.get("/health")
async def health():
    """Local readiness check that never exposes credential values."""
    return {
        "status": "ok",
        "configured": {
            "rtc": bool(settings.RTC_APP_ID and settings.RTC_APP_KEY),
            "speech": bool(settings.SPEECH_APP_ID),
            "ark": bool(settings.ARK_ENDPOINT_ID and settings.ARK_API_KEY),
            "knowledge_base": bool(
                settings.VOLC_AK
                and settings.VOLC_SK
                and settings.VOLC_ACCOUNT_ID
                and settings.KB_COLLECTION_NAME
            ),
            "public_callback": bool(
                settings.SERVER_URL and settings.CALLBACK_AUTH_TOKEN
            ),
        },
    }


# --- 1. 获取场景 (前端展示用) ---
@app.post("/getScenes")
async def get_scenes(request: Request):
    if not settings.RTC_APP_ID or not settings.RTC_APP_KEY:
        raise HTTPException(
            status_code=503,
            detail="RTC 尚未配置：请先将 .env.example 复制为 .env，并填写 RTC_APP_ID 与 RTC_APP_KEY。",
        )

    room_id = settings.RTC_ROOM_ID
    user_id = settings.RTC_USER_ID

    # 签发 RTC Token
    token_builder = AccessToken(
        settings.RTC_APP_ID, settings.RTC_APP_KEY, room_id, user_id
    )
    token_builder.add_privilege(PRIVILEGES["PrivSubscribeStream"], 0)
    token_builder.add_privilege(PRIVILEGES["PrivPublishStream"], 0)
    token_builder.expire_time(int(time.time()) + 3600 * 24)
    token = token_builder.serialize()

    # 构造返回结构
    return {
        "ResponseMetadata": {"Action": "getScenes"},
        "Result": {
            "scenes": [
                {
                    "scene": {
                        # --- 补全的核心字段 ---
                        "id": "Custom",  # 建议改为 Custom，通常前端会根据这个 ID 做特殊处理
                        "name": "懂小智课程顾问",
                        # 必须与 StartVoiceChat 的 AgentConfig.UserId 保持一致，
                        # 否则前端会把智能体字幕当作未知用户消息过滤掉。
                        "botName": settings.RTC_AGENT_USER_ID,
                        "icon": "https://lf3-rtc-demo.volccdn.com/obj/rtc-aigc-assets/DoubaoAvatar.png",  # 补全图标
                        # --- 功能开关 ---
                        "isInterruptMode": True,  # 是否支持打断
                        "isVision": False,  # 补全：是否开启视觉（摄像头）
                        "isScreenMode": False,  # 补全：是否开启屏幕共享
                        # --- 数字人相关 (无数字人时设为 None/null) ---
                        "isAvatarScene": None,
                        "avatarBgUrl": None,
                    },
                    "rtc": {
                        "AppId": settings.RTC_APP_ID,
                        "RoomId": room_id,
                        "UserId": user_id,
                        "Token": token,
                    },
                    # 这里的配置主要是为了兼容前端透传，实际生效主要看 proxy
                    "VoiceChat": {},
                }
            ]
        },
    }


# --- 2. 拦截前端的 StartVoiceChat 请求 (核心配置下发) ---
# main.py 核心修改
# rag_llm_server/main.py


@app.post("/proxy")
async def proxy(request: Request):
    """
    将前端的 RTC 操作转换为火山引擎 OpenAPI 请求。
    """
    action = request.query_params.get("Action")
    version = request.query_params.get("Version", "2024-12-01")
    allowed_actions = {"StartVoiceChat", "StopVoiceChat"}
    if action not in allowed_actions:
        raise HTTPException(status_code=400, detail="不支持的 RTC 操作")

    required_values = {
        "VOLC_ACCESS_KEY": settings.VOLC_AK,
        "VOLC_SECRET_KEY": settings.VOLC_SK,
        "RTC_APP_ID": settings.RTC_APP_ID,
        "SPEECH_APP_ID": settings.SPEECH_APP_ID,
        "SERVER_URL": settings.SERVER_URL,
        "CALLBACK_AUTH_TOKEN": settings.CALLBACK_AUTH_TOKEN,
    }
    missing_values = [name for name, value in required_values.items() if not value]
    if missing_values:
        raise HTTPException(
            status_code=503,
            detail=f"RTC 服务配置不完整，缺少：{', '.join(missing_values)}",
        )

    # 打印前端实际传过来的数据，方便观察
    incoming_body = {}
    try:
        incoming_body = await request.json()
        print(f"DEBUG: 收到前端请求 {action}, Body: {incoming_body}")
    except ValueError:
        pass

    target_app_id = settings.RTC_APP_ID
    target_room_id = settings.RTC_ROOM_ID
    target_user_id = settings.RTC_USER_ID

    request_body = {}

    print(f"RTCCCCC  callback {settings.SERVER_URL}/api/chat_callback")
    if action == "StartVoiceChat":
        request_body = {
            "AppId": target_app_id,
            "RoomId": target_room_id,
            "TaskId": settings.RTC_TASK_ID,
            "AgentConfig": {
                "TargetUserId": [target_user_id],
                "WelcomeMessage": settings.WELCOME_MESSAGE,
                "UserId": settings.RTC_AGENT_USER_ID,
                "EnableConversationStateCallback": True, 
            },
            "Config": {
                "ASRConfig": {
                    "Provider": "volcano",
                    "ProviderParams": {
                        "Mode": "smallmodel",
                        "AppId": settings.SPEECH_APP_ID,
                        "Cluster": "volcengine_streaming_common",
                    },
                },
                "TTSConfig": {
                    "Provider": "volcano",
                    "ProviderParams": {
                        "app": {
                            "appid": settings.SPEECH_APP_ID,
                            "cluster": "volcano_tts",
                        },
                        "audio": {
                            "voice_type": "BV001_streaming",
                            "speed_ratio": 1,
                            "pitch_ratio": 1,
                            "volume_ratio": 1,
                        },
                    },
                },
                "LLMConfig": {
                    # 先用 Custom 模式测试你的回调地址
                    "Mode": "CustomLLM",
                    "Url": f"{settings.SERVER_URL}/api/chat_callback",
                    "APIKey": settings.CALLBACK_AUTH_TOKEN,
                    "Method": "POST",
                    "ApiType": "https"
                    if str(settings.SERVER_URL).startswith("https")
                    else "http",
                },
                # 将用户与 AI 的实时字幕通过 RTC 二进制消息发给前端。
                # 当前页面是非数字人场景，前端按 SubtitleMode=0 组装字幕。
                "SubtitleConfig": {
                    "DisableRTSSubtitle": False,
                    "SubtitleMode": 0,
                },
                "InterruptMode": 0,
            },
        }
    elif action == "StopVoiceChat":
        request_body = {
            "AppId": target_app_id,
            "RoomId": target_room_id,
            "TaskId": settings.RTC_TASK_ID,
        }
    else:
        # 其他 Action 直接返回前端传的内容
        request_body = incoming_body

    # --- 签名与发送 ---
    host = "rtc.volcengineapi.com"
    open_api_request_data = {
        "method": "POST",
        "path": "/",
        "params": {"Action": action, "Version": version},
        "headers": {"Host": host, "Content-Type": "application/json"},
        "body": request_body,
    }

    # 这里的 AK/SK 必须拥有调用 RTC OpenAPI 的权限
    account_config = {"accessKeyId": settings.VOLC_AK, "secretKey": settings.VOLC_SK}

    signer = Signer(open_api_request_data, "rtc")
    signer.add_authorization(account_config)

    url = f"https://{host}?Action={action}&Version={version}"

    # print(f"DEBUG: 发送请求到 {url} callback rtc")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=open_api_request_data["headers"],
            json=request_body,
            timeout=30.0,
        )
        result = resp.json()
        print(f"DEBUG: 火山引擎返回结果: {result}")
        return result


# --- 3. 业务回调接口 (RTC -> 这里) ---


# ... 其他代码 ...


@app.post("/api/chat_callback")
async def chat_callback(request: Request):
    return await build_chat_callback_response(request)


# 1. 定义消息模型
class ChatMessage(BaseModel):
    role: str  # "user" 或 "assistant"
    content: str


class DebugRequest(BaseModel):
    history: List[ChatMessage] = Field(default_factory=list)
    question: str


# 2. 调试接口
@app.post("/debug/chat")
async def debug_chat(request: DebugRequest):
    require_debug_mode()

    # 构造当前发送给 LLM 的消息列表
    current_messages = []
    for msg in request.history:
        current_messages.append({"role": msg.role, "content": msg.content})

    # 放入用户最新问题
    current_messages.append({"role": "user", "content": request.question})

    async def generate_text():
        full_ai_response = ""
        total_usage = None

            # 1. 记录总开始时间
        start_t = time.time()
        # 查询知识库
        rag_content = await rag_service.retrieve(request.question)

        rag_duration = time.time() - start_t

        print(f"DEBUG: 知识库查询耗时: {rag_duration:.2f}s")
        # print(f"DEBUG: 知识库返回检索内容: {rag_content}")

        # 2. 记录 LLM 调用开始时间
        llm_start_t = time.time()

        # 调用 llm_service
        stream = llm_service.chat_stream(current_messages, rag_content)

        for chunk in stream:
            if chunk and chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    content = delta.content
                    full_ai_response += content  # 累积 AI 的回答
                    yield content
            # 记录 Token 消耗
            if hasattr(chunk, "usage") and chunk.usage:
                total_usage = chunk.usage

        # 3. 记录 LLM 调用耗时
        llm_duration = time.time() - llm_start_t
        print(f"DEBUG: LLM 调用耗时: {llm_duration:.2f}s")

        if total_usage:
            print(
                f"🎫 Token 统计: Total={total_usage.total_tokens} (P:{total_usage.prompt_tokens}, C:{total_usage.completion_tokens})"
            )

        # --- 重点：在流结束后构造并打印 history 结构 ---
        # 构造完整的 history 列表
        new_history = []
        # 添加旧历史
        for m in request.history:
            new_history.append({"role": m.role, "content": m.content})
        # 添加最新的一轮对话
        new_history.append({"role": "user", "content": request.question})
        new_history.append({"role": "assistant", "content": full_ai_response})

        # 打印到控制台，方便你直接复制
        print("\n" + "=" * 50)
        print("🐞 调试完成！以下是可用于下次请求的 history 结构：")
        print(json.dumps({"history": new_history}, ensure_ascii=False, indent=2))
        print("=" * 50 + "\n")

    return StreamingResponse(generate_text(), media_type="text/plain")


# --- 新增：知识库调试接口 ---
@app.get("/debug/rag")
async def debug_rag(query: str):
    """
    调试接口：直接返回知识库检索到的原始文本内容
    用法：浏览器访问 http://127.0.0.1:3001/debug/rag?query=你的问题
    """
    require_debug_mode()
    if not query:
        return {"error": "请提供 query 参数"}

    print(f"🔍 [Debug] 正在检索知识库: {query}")

    # 调用我们在 rag_service.py 中实现的异步 retrieve 方法
    context = await rag_service.retrieve(query)

    return {
        "query": query,
        "retrieved_context": context,
        "length": len(context) if context else 0,
        "status": "success" if context else "no_results_or_error",
    }


frontend_build_dir = Path(
    settings.FRONTEND_BUILD_DIR
    or Path(__file__).resolve().parents[1] / "build"
).resolve()
frontend_index = frontend_build_dir / "index.html"
backend_path_roots = {
    "api",
    "debug",
    "docs",
    "getScenes",
    "health",
    "openapi.json",
    "proxy",
    "redoc",
}

if frontend_index.is_file():
    static_dir = frontend_build_dir / "static"
    if static_dir.is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=static_dir),
            name="frontend-static",
        )

    @app.get("/", include_in_schema=False)
    async def frontend_root():
        return FileResponse(frontend_index)

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend_fallback(frontend_path: str):
        first_segment = frontend_path.split("/", 1)[0]
        if first_segment in backend_path_roots:
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = (frontend_build_dir / frontend_path).resolve()
        try:
            candidate.relative_to(frontend_build_dir)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")

        if candidate.is_file():
            return FileResponse(candidate)

        # Browser routes fall back to the SPA shell. Missing files should remain
        # a real 404 so caching layers do not store index.html as an asset.
        if Path(frontend_path).suffix:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(frontend_index)


if __name__ == "__main__":
    import uvicorn

    print(f"🚀 Server running at {settings.SERVER_URL}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3001,
        reload=True,
        reload_dirs=[".", "services"],
        # 依然建议排除缓存文件，防止编译行为触发重启
        reload_excludes=[
            "*/__pycache__/*",
            "*.pyc",
            ".venv/*",  # 排除根目录下的虚拟环境
            "*/.venv/*",
        ],
    )
