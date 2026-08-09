#!/usr/bin/env python3
"""Update only SERVER_URL in a dotenv file without exposing other values."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlparse


def update_server_url(env_path: Path, public_url: str) -> None:
    parsed_url = urlparse(public_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("SERVER_URL 必须是合法的 HTTPS 地址")
    if not env_path.is_file():
        raise FileNotFoundError(f"未找到环境变量文件：{env_path}")

    original_text = env_path.read_text(encoding="utf-8")
    lines = original_text.splitlines()
    replacement = f"SERVER_URL={public_url.rstrip('/')}"
    updated = False

    for index, line in enumerate(lines):
        if line.startswith("SERVER_URL="):
            lines[index] = replacement
            updated = True
            break

    if not updated:
        lines.append(replacement)

    output = "\n".join(lines) + "\n"
    file_mode = env_path.stat().st_mode
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=env_path.parent,
        delete=False,
    ) as temporary_file:
        temporary_file.write(output)
        temporary_path = Path(temporary_file.name)

    os.chmod(temporary_path, file_mode)
    os.replace(temporary_path, env_path)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("用法：update_server_url.py <.env 路径> <HTTPS URL>")
    update_server_url(Path(sys.argv[1]), sys.argv[2])


if __name__ == "__main__":
    main()
