import struct
from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from main import app
from services.token_build import ByteBuf


class TokenSerializationTests(unittest.TestCase):
    def test_privilege_keys_are_serialized_in_numeric_order(self):
        """RTC signatures depend on matching the official Node key order."""
        privileges = {4: 40, 0: 0, 3: 30, 1: 10, 2: 20}

        packed = ByteBuf().put_tree_map_uint32(privileges).pack()
        item_count = struct.unpack_from("<H", packed, 0)[0]
        keys = [
            struct.unpack_from("<H", packed, 2 + index * 6)[0]
            for index in range(item_count)
        ]

        self.assertEqual(keys, [0, 1, 2, 3, 4])


class SceneConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.original_app_id = settings.RTC_APP_ID
        self.original_app_key = settings.RTC_APP_KEY
        self.original_agent_user_id = settings.RTC_AGENT_USER_ID
        settings.RTC_APP_ID = "test-app-id"
        settings.RTC_APP_KEY = "test-app-key"
        settings.RTC_AGENT_USER_ID = "TestAgent"

    def tearDown(self):
        settings.RTC_APP_ID = self.original_app_id
        settings.RTC_APP_KEY = self.original_app_key
        settings.RTC_AGENT_USER_ID = self.original_agent_user_id

    def test_scene_bot_name_matches_rtc_agent_user_id(self):
        """Mismatched IDs make the frontend discard valid AI subtitles."""
        response = TestClient(app).post("/getScenes", json={})

        self.assertEqual(response.status_code, 200)
        scene = response.json()["Result"]["scenes"][0]["scene"]
        self.assertEqual(scene["botName"], "TestAgent")


class LocalApiSecurityTests(unittest.TestCase):
    def test_proxy_rejects_unsupported_rtc_action(self):
        response = TestClient(app).post("/proxy?Action=UnsupportedAction", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "不支持的 RTC 操作")

    def test_cors_allows_only_the_local_frontend(self):
        client = TestClient(app)
        local_response = client.options(
            "/getScenes",
            headers={
                "Origin": "http://127.0.0.1:4173",
                "Access-Control-Request-Method": "POST",
            },
        )
        unknown_response = client.options(
            "/getScenes",
            headers={
                "Origin": "https://untrusted.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(
            local_response.headers.get("access-control-allow-origin"),
            "http://127.0.0.1:4173",
        )
        self.assertIsNone(unknown_response.headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()
