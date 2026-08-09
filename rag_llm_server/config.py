import os
from dotenv import load_dotenv

load_dotenv()


def resolve_server_url() -> str | None:
    """Resolve the public callback URL across local and hosted environments."""
    explicit_url = os.getenv("SERVER_URL")
    if explicit_url:
        return explicit_url.rstrip("/")

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url.rstrip("/")

    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        return f"https://{railway_domain.strip('/')}"

    return None


def resolve_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", "")
    origins = {
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    }
    origins.update(
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    )
    return sorted(origins)


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    FRONTEND_BUILD_DIR = os.getenv("FRONTEND_BUILD_DIR")
    CORS_ORIGINS = resolve_cors_origins()

    VOLC_AK = os.getenv("VOLC_ACCESS_KEY")
    VOLC_SK = os.getenv("VOLC_SECRET_KEY")
    ARK_ENDPOINT_ID = os.getenv("ARK_ENDPOINT_ID")
    ARK_API_KEY = os.getenv("ARK_API_KEY")

    RTC_APP_ID = os.getenv("RTC_APP_ID")
    RTC_APP_KEY = os.getenv("RTC_APP_KEY")

    RTC_ROOM_ID = os.getenv("RTC_ROOM_ID", "ChatRoom01")
    RTC_USER_ID = os.getenv("RTC_USER_ID", "Huoshan01")
    RTC_TASK_ID = os.getenv("RTC_TASK_ID", "ChatTask01")
    RTC_AGENT_USER_ID = os.getenv("RTC_AGENT_USER_ID", "AiAgent")

    SPEECH_APP_ID = os.getenv("SPEECH_APP_ID")
    SERVER_URL = resolve_server_url()
    CALLBACK_AUTH_TOKEN = os.getenv("CALLBACK_AUTH_TOKEN")

    KB_COLLECTION_NAME = os.getenv("KB_COLLECTION_NAME")
    KB_PROJECT_NAME = os.getenv("KB_PROJECT_NAME", "default")
    VOLC_ACCOUNT_ID = os.getenv("VOLC_ACCOUNT_ID")

    WELCOME_MESSAGE = os.getenv(
        "WELCOME_MESSAGE",
        "我是懂小智，你的专属课程顾问，有什么问题可以直接问我。",
    )


settings = Config()
