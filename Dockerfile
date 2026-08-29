# ========== 后端 ==========
FROM python:3.11-slim AS backend

WORKDIR /app/server

# 安装依赖
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码（包含 .env 同级目录的上级）
COPY server/ ./
COPY server/.env /app/.env

EXPOSE 8000
CMD ["python", "main.py"]

# ========== 前端 ==========
FROM node:18-alpine AS frontend-build

WORKDIR /app/client
COPY client/package*.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# ========== 最终镜像 ==========
FROM python:3.11-slim

WORKDIR /app

# 安装 Nginx
RUN apt-get update && apt-get install -y --no-install-recommends nginx curl && \
    rm -rf /var/lib/apt/lists/*

# 后端
COPY --from=backend /app/server /app/server
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# 前端
COPY --from=frontend-build /app/client/dist /var/www/html

# Nginx 配置
COPY nginx.conf /etc/nginx/sites-available/default

# 暴露端口
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
