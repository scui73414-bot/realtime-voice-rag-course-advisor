from fastapi import FastAPI, Request

from config import settings
from services.chat_callback import build_chat_callback_response


# This app is intentionally small: ngrok exposes only this process, never the
# local Swagger, RTC proxy, token-issuing endpoint, or other debugging routes.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "callback_auth_configured": bool(settings.CALLBACK_AUTH_TOKEN),
    }


@app.post("/api/chat_callback")
async def chat_callback(request: Request):
    return await build_chat_callback_response(request)
