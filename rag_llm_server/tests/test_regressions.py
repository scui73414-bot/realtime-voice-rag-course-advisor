import json
import os
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from config import resolve_server_url, settings
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

    def test_debug_endpoints_are_hidden_in_production(self):
        original_app_env = settings.APP_ENV
        settings.APP_ENV = "production"
        try:
            client = TestClient(app)
            chat_response = client.post(
                "/debug/chat",
                json={"history": [], "question": "test"},
            )
            rag_response = client.get("/debug/rag", params={"query": "test"})
        finally:
            settings.APP_ENV = original_app_env

        self.assertEqual(chat_response.status_code, 404)
        self.assertEqual(rag_response.status_code, 404)


class HostedConfigurationTests(unittest.TestCase):
    def test_explicit_server_url_has_priority(self):
        with patch.dict(
            os.environ,
            {
                "SERVER_URL": "https://explicit.example.com/",
                "RENDER_EXTERNAL_URL": "https://render.example.com",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_server_url(),
                "https://explicit.example.com",
            )

    def test_render_url_is_used_without_an_explicit_url(self):
        with patch.dict(
            os.environ,
            {
                "SERVER_URL": "",
                "RENDER_EXTERNAL_URL": "https://demo.onrender.com/",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_server_url(),
                "https://demo.onrender.com",
            )

    def test_production_static_routes_do_not_shadow_backend_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir)
            (build_dir / "index.html").write_text(
                "<!doctype html><title>demo</title>",
                encoding="utf-8",
            )
            script = """
import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
print(json.dumps({
    "root": client.get("/").status_code,
    "spa": client.get("/conversation/demo").status_code,
    "docs": client.get("/docs").status_code,
    "asset": client.get("/missing.js").status_code,
}))
"""
            env = os.environ.copy()
            env.update(
                {
                    "APP_ENV": "production",
                    "FRONTEND_BUILD_DIR": str(build_dir),
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=BACKEND_DIR,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            json.loads(result.stdout.strip()),
            {"root": 200, "spa": 200, "docs": 404, "asset": 404},
        )


if __name__ == "__main__":
    unittest.main()
