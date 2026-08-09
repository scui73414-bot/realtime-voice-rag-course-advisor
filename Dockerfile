FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
ENV DISABLE_ESLINT_PLUGIN=true
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    FRONTEND_BUILD_DIR=/app/build \
    PORT=10000

WORKDIR /app
COPY rag_llm_server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY rag_llm_server /app/rag_llm_server
COPY --from=frontend-builder /app/build /app/build

WORKDIR /app/rag_llm_server
EXPOSE 10000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
