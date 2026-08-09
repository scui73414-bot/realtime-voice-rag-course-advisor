#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/rag_llm_server"
RUNTIME_DIR="$PROJECT_DIR/.runtime"
ENV_FILE="$BACKEND_DIR/.env"

if [[ -f "$SCRIPT_DIR/dev.local" ]]; then
  # Machine-specific executable paths only; this file is ignored by Git.
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/dev.local"
fi

PYTHON_BIN="${PYTHON_BIN:-$BACKEND_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi

NGROK_BIN="${NGROK_BIN:-$(command -v ngrok || true)}"
NODE_BIN="${NODE_BIN:-$(command -v node || true)}"
CRACO_JS="$PROJECT_DIR/node_modules/@craco/craco/dist/bin/craco.js"

pid_file() {
  printf '%s/%s.pid' "$RUNTIME_DIR" "$1"
}

log_file() {
  printf '%s/%s.log' "$RUNTIME_DIR" "$1"
}

read_pid() {
  local file
  file="$(pid_file "$1")"
  [[ -f "$file" ]] && tr -d '[:space:]' < "$file"
}

is_running() {
  local pid
  pid="$(read_pid "$1")"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

port_is_busy() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempts="${3:-40}"

  for ((index = 1; index <= attempts; index++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done

  echo "启动失败：$name 未能通过健康检查。查看 $(log_file "$name")" >&2
  return 1
}

require_start_dependencies() {
  if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    echo "未找到可用的 Python。请复制 scripts/dev.local.example 为 scripts/dev.local 并配置 PYTHON_BIN。" >&2
    exit 1
  fi
  if [[ -z "$NGROK_BIN" || ! -x "$NGROK_BIN" ]]; then
    echo "未找到 ngrok。请安装 ngrok，或在 scripts/dev.local 中配置 NGROK_BIN。" >&2
    exit 1
  fi
  if [[ -z "$NODE_BIN" || ! -x "$NODE_BIN" ]]; then
    echo "未找到 Node.js。请在 scripts/dev.local 中配置 NODE_BIN。" >&2
    exit 1
  fi
  if [[ ! -f "$CRACO_JS" ]]; then
    echo "未找到前端依赖，请先在项目根目录运行 npm install。" >&2
    exit 1
  fi
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "未找到 rag_llm_server/.env，请先从 .env.example 复制并填写配置。" >&2
    exit 1
  fi
}

ensure_ports_available() {
  local port
  for port in 3001 3002 4040 4173; do
    if port_is_busy "$port"; then
      echo "端口 $port 已被其他进程占用。请先运行 scripts/dev.sh status 检查。" >&2
      exit 1
    fi
  done
}

start_process() {
  local name="$1"
  shift
  "$@" >"$(log_file "$name")" 2>&1 &
  echo "$!" >"$(pid_file "$name")"
}

discover_public_url() {
  "$PYTHON_BIN" - <<'PY'
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as response:
    tunnels = json.load(response).get("tunnels", [])

for tunnel in tunnels:
    public_url = tunnel.get("public_url", "")
    if public_url.startswith("https://"):
        print(public_url)
        break
else:
    raise SystemExit(1)
PY
}

start_all() {
  mkdir -p "$RUNTIME_DIR"
  require_start_dependencies

  if is_running main || is_running callback || is_running ngrok || is_running frontend; then
    echo "项目已经由启动脚本运行。使用 scripts/dev.sh status 查看状态。"
    exit 0
  fi

  ensure_ports_available
  # One foreground supervisor keeps all four children tied to this terminal.
  # Closing it or pressing Ctrl-C therefore cleans up the whole environment.
  trap 'stop_all >/dev/null 2>&1' INT TERM EXIT

  echo "[1/4] 启动 HTTPS 隧道"
  start_process ngrok "$NGROK_BIN" http 3002 --log stdout --log-format json
  wait_for_url ngrok "http://127.0.0.1:4040/api/tunnels"

  local public_url=""
  for _ in {1..40}; do
    public_url="$(discover_public_url 2>/dev/null || true)"
    if [[ -n "$public_url" ]]; then
      break
    fi
    sleep 0.25
  done
  if [[ -z "$public_url" ]]; then
    echo "启动失败：ngrok 未能生成 HTTPS 地址。查看 $(log_file ngrok)" >&2
    return 1
  fi
  "$PYTHON_BIN" "$SCRIPT_DIR/update_server_url.py" "$ENV_FILE" "$public_url"
  echo "      已更新 SERVER_URL（未显示凭证）"

  echo "[2/4] 启动公网回调服务"
  (
    cd "$BACKEND_DIR"
    start_process callback "$PYTHON_BIN" -m uvicorn public_callback:app --host 127.0.0.1 --port 3002
  )
  wait_for_url callback "http://127.0.0.1:3002/health"

  echo "[3/4] 启动本地业务服务"
  (
    cd "$BACKEND_DIR"
    start_process main "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port 3001
  )
  wait_for_url main "http://127.0.0.1:3001/health"

  echo "[4/4] 启动前端"
  # CRACO starts a child process by the command name `node`, so expose the
  # selected Node runtime on PATH in addition to invoking it explicitly.
  start_process frontend env PORT=4173 DISABLE_ESLINT_PLUGIN=true \
    PATH="$(dirname "$NODE_BIN"):$PATH" \
    "$NODE_BIN" "$CRACO_JS" start --host 0.0.0.0
  wait_for_url frontend "http://127.0.0.1:4173/" 120

  echo
  echo "项目启动完成："
  echo "  语音页面  http://127.0.0.1:4173/"
  echo "  Swagger   http://127.0.0.1:3001/docs"
  echo "  运行日志  $RUNTIME_DIR"
  echo "  按 Ctrl-C 可一次停止全部服务"

  while is_running ngrok && is_running callback && is_running main && is_running frontend; do
    sleep 2
  done

  echo "有服务意外退出，正在清理其余进程。" >&2
  return 1
}

stop_one() {
  local name="$1"
  local pid
  pid="$(read_pid "$name")"

  if [[ -z "$pid" ]]; then
    return 0
  fi

  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
  fi
  rm -f "$(pid_file "$name")"
}

stop_all() {
  echo "正在停止本地开发服务……"
  stop_one frontend
  stop_one main
  stop_one callback
  stop_one ngrok
  echo "已停止。日志保留在 $RUNTIME_DIR。"
}

show_status() {
  local name
  for name in ngrok callback main frontend; do
    if is_running "$name"; then
      echo "$name: running (PID $(read_pid "$name"))"
    else
      echo "$name: stopped"
    fi
  done
}

case "${1:-start}" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    show_status
    ;;
  *)
    echo "用法：scripts/dev.sh {start|stop|restart|status}" >&2
    exit 2
    ;;
esac
