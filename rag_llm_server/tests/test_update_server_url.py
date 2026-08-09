from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from update_server_url import update_server_url  # noqa: E402


class UpdateServerUrlTests(unittest.TestCase):
    def test_only_server_url_is_replaced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ARK_API_KEY=keep-this-value\n"
                "SERVER_URL=https://old.example.com\n"
                "CALLBACK_AUTH_TOKEN=keep-this-token\n",
                encoding="utf-8",
            )

            update_server_url(env_path, "https://new.example.com/")

            self.assertEqual(
                env_path.read_text(encoding="utf-8"),
                "ARK_API_KEY=keep-this-value\n"
                "SERVER_URL=https://new.example.com\n"
                "CALLBACK_AUTH_TOKEN=keep-this-token\n",
            )

    def test_non_https_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("SERVER_URL=\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                update_server_url(env_path, "http://example.com")


if __name__ == "__main__":
    unittest.main()
