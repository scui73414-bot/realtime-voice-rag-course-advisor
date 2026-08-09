# 稳定 HTTPS 部署

本项目推荐将 React 与 FastAPI 构建到同一个 Docker 容器，并由一个 HTTPS
域名同时提供页面、RTC 控制接口和 CustomLLM 流式回调。这样可以避免跨域、
双服务地址同步和 ngrok 地址变化问题。

## Render Blueprint

仓库根目录的 `render.yaml` 会创建一个新加坡区域的 Docker Web Service：

- 自动签发 `onrender.com` HTTPS 域名；
- 使用 `/health` 做健康检查；
- GitHub CI 通过后才自动部署；
- 自动生成 `CALLBACK_AUTH_TOKEN`；
- 自动读取 Render 提供的 `RENDER_EXTERNAL_URL` 作为 RTC 回调地址。

在 Render 创建 Blueprint 后，只需要在控制台填写标记为 `sync: false` 的
火山引擎配置。不要将真实值写入 `render.yaml` 或 GitHub。

需要填写的变量：

- `VOLC_ACCESS_KEY`、`VOLC_SECRET_KEY`
- `ARK_ENDPOINT_ID`、`ARK_API_KEY`
- `RTC_APP_ID`、`RTC_APP_KEY`
- `SPEECH_APP_ID`
- `KB_COLLECTION_NAME`、`VOLC_ACCOUNT_ID`

部署完成后依次验证：

1. `https://<service>.onrender.com/health` 返回 `status: ok`；
2. 项目首页可以正常加载；
3. 浏览器允许麦克风后能够加入 RTC 房间；
4. 用户字幕、RAG 回答、AI 语音和 AI 字幕均正常。

## 免费实例限制

Render 免费 Web Service 闲置 15 分钟后会休眠，首次请求唤醒可能需要约一分钟。
它适合学习和作品集预览，但不适合需要随时保持 8 秒内响应的正式演示。面试或
录屏前先访问 `/health` 完成预热；需要常驻时再升级为付费实例。

## 本地生产模式验证

前端完成 `npm run build` 后，可用以下方式验证同域部署：

```bash
cd rag_llm_server
APP_ENV=production FRONTEND_BUILD_DIR=../build \
  uvicorn main:app --host 127.0.0.1 --port 3001
```

生产模式下 `/docs`、`/debug/chat` 和 `/debug/rag` 不对外开放。
