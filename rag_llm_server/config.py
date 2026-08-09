import os
from dotenv import load_dotenv

load_dotenv()

class Config:
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
    SERVER_URL = os.getenv("SERVER_URL")
    CALLBACK_AUTH_TOKEN = os.getenv("CALLBACK_AUTH_TOKEN")

    KB_COLLECTION_NAME = os.getenv("KB_COLLECTION_NAME")
    KB_PROJECT_NAME = os.getenv("KB_PROJECT_NAME", "default")
    VOLC_ACCOUNT_ID = os.getenv("VOLC_ACCOUNT_ID")

    WELCOME_MESSAGE = os.getenv(
        "WELCOME_MESSAGE",
        "我是懂小智，你的专属课程顾问，有什么问题可以直接问我。",
    )

settings = Config()
