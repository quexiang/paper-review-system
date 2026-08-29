# 📝 学术论文审稿系统

> AI 深度审阅 + 逻辑连贯性审查 + 修订痕迹 + 自动补全 + 论文润色 + 文献综述 + 期刊推荐

## 功能特性

- **📄 多格式支持**：PDF / DOCX / TXT / Markdown 文件解析提取
- **🤖 多模型选择**：界面切换不同大模型，支持 OpenAI Compatible API / 本地 Ollama / 自定义端点
- **📋 规则引擎**：章节完整性检测 + 引用匹配，精准识别关键问题
- **🧠 AI 深度审阅**：LLM 逐章节语义分析，每条 ≥ 300 字，按内容质量/写作水平/具体问题/优点四维评审
- **🔍 逻辑连贯性审查**：章节逻辑、论点论据逻辑、语句连贯性检测、主题一致性评价、知识图谱可视化
- **✍️ 修订痕迹**：增/删/改对比展示，≥ 8 条具体修改建议，标注位置和详细理由
- **📝 自动补全**：检测缺失或内容不足的章节，AI 生成补全草稿
- **✨ 论文润色**：逐章 SCI 级语言润色，严格保留技术内容和术语
- **📖 文献综述**：基于论文内容自动生成完整学术文献综述
- **📚 期刊推荐**：智能推荐 Top 10 投稿期刊，含 IF/接受率/审稿周期
- **📥 报告下载**：一键下载 DOCX 审稿报告（含修改痕迹、批注、推荐期刊）
- **📊 评分报告**：总体评分 + 优点/弱点分析 + 接收建议

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite |
| 后端 | Python FastAPI + uvicorn |
| AI | OpenAI Compatible API（LiteLLM 代理 / Ollama / Claude / GPT） |
| PDF 解析 | pypdfium2 |
| DOCX 生成 | python-docx |

## 架构概览

```
浏览器 (端口 3000)  ──Nginx──▶  静态文件
                                │
                                └──/api/*──▶  FastAPI 后端 (端口 8000)
                                                    │
                                                    └──▶  LiteLLM 代理 (端口 7000) / LLM
```

---

## 环境要求

| 软件 | 最低版本 | 说明 |
|---|---|---|
| Python | ≥ 3.11 | 后端运行环境 |
| Node.js | ≥ 18 | 前端构建 |
| Nginx | ≥ 1.18 | 生产环境反向代理（可选） |
| LiteLLM | 最新 | LLM 代理，用于统一 API 接口 |

---

## 一、后端部署

### 1. 安装 Python 依赖

```bash
cd /path/to/paper-review-system/server

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate    # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

依赖文件 `requirements.txt` 内容：

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
aiofiles>=24.0.0
openai>=1.70.0
python-docx
python-dotenv>=1.0.0
pypdfium2
```

### 2. 配置环境变量

在 `/path/to/paper-review-system/` 目录下创建 `.env` 文件：

```bash
cd /path/to/paper-review-system
cp .env .env.bak  # 备份示例

# 编辑 .env 文件
vi .env
```

**开发环境示例**（使用本地 Ollama）：

```bash
# OpenAI Compatible API
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3.6:latest

# 管理员认证
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_strong_password_here
```

**生产环境示例**（使用 LiteLLM 代理）：

```bash
# OpenAI Compatible API（LiteLLM 代理）
OPENAI_API_KEY=your-sk-key
OPENAI_BASE_URL=http://127.0.0.1:7000
MODEL_NAME=claude-sonnet-4-5-20251001

# 管理员认证（生产环境必须修改）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_to_a_strong_password

# JWT 密钥（生产环境必须设置，生成随机字符串）
JWT_SECRET=your-256-bit-secret-key-generate-with-python-secret

# 后端服务端口
SERVER_PORT=8000
```

### 3. 启动 LiteLLM 代理

```bash
# 安装 LiteLLM
pip install litellm

# 创建配置文件 config.yaml
cat > litellm_config.yaml << 'EOF'
model_list:
  - model_name: claude-sonnet-4-5-20251001
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20251001
      api_key: sk-your-openai-compatible-key
  - model_name: claude-opus-4-5-20251001
    litellm_params:
      model: anthropic/claude-opus-4-5-20251001
      api_key: sk-your-openai-compatible-key
  - model_name: claude-haiku-4-5-20251001
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: sk-your-openai-compatible-key
EOF

# 启动（端口 7000）
litellm --config litellm_config.yaml --port 7000 &

# 或使用 systemd 保持后台运行
# 见下方"使用 systemd 管理"一节
```

### 4. 验证后端

```bash
cd server
python -c "from main import app; print('OK')"
curl http://localhost:8000/api/health
# 应返回: {"status":"ok","service":"paper-review-system"}
```

### 5. 使用 systemd 管理后端

创建服务文件：

```bash
sudo tee /etc/systemd/system/paper-review-server.service > /dev/null << 'EOF'
[Unit]
Description=Paper Review System - Backend API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/paper-review-system/server
Environment=PATH=/path/to/paper-review-system/server/venv/bin
EnvironmentFile=/path/to/paper-review-system/.env
ExecStart=/path/to/paper-review-system/server/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable paper-review-server
sudo systemctl start paper-review-server
sudo systemctl status paper-review-server
```

---

## 二、前端部署

### 1. 安装 Node.js 依赖

```bash
cd /path/to/paper-review-system/client

# 使用 npm
npm install

# 或使用 yarn
yarn install
```

### 2. 配置生产环境

编辑 `vite.config.ts`，将代理目标改为 Nginx 反代端口（生产环境由 Nginx 处理 API 转发）：

```bash
# 生产构建时，vite.config.ts 中的代理配置不生效
# 生产环境依赖 Nginx 同时代理静态文件和 /api/* 请求到后端
```

### 3. 构建前端

```bash
cd /path/to/paper-review-system/client

# 构建生产版本，输出到 dist/ 目录
npm run build

# 输出目录结构：
# dist/
# ├── assets/     # JS/CSS 文件
# ├── index.html  # 入口文件
# └── vite.svg    # 静态资源
```

---

## 三、Nginx 部署（生产环境推荐）

### 1. 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx

# macOS
brew install nginx
```

### 2. 配置 Nginx

```bash
sudo tee /etc/nginx/sites-available/paper-review > /dev/null << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 替换为实际域名

    # 前端静态文件
    location / {
        root /path/to/paper-review-system/client/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 文件上传支持
        client_max_body_size 50M;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 日志
    access_log /var/log/nginx/paper-review-access.log;
    error_log /var/log/nginx/paper-review-error.log;
}
EOF

# 启用配置
sudo ln -s /etc/nginx/sites-available/paper-review /etc/nginx/sites-enabled/paper-review

# 测试并重启
sudo nginx -t
sudo systemctl restart nginx
```

### 3. 配置 HTTPS（Let's Encrypt）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期（Certbot 通常已配置 cron 任务）
sudo certbot renew --dry-run
```

---

## 四、使用 systemd 管理 LiteLLM 代理

```bash
sudo tee /etc/systemd/system/litellm.service > /dev/null << 'EOF'
[Unit]
Description=LiteLLM Proxy Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/opt/litellm
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/local/bin/litellm --config /opt/litellm/litellm_config.yaml --port 7000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable litellm
sudo systemctl start litellm
sudo systemctl status litellm
```

---

## 五、完整一键部署脚本

以下脚本适用于全新服务器的一键部署：

```bash
#!/bin/bash
set -e

# ============ 配置参数 ============
PROJECT_DIR="/opt/paper-review-system"
NGINX_PORT=80
DOMAIN="your-domain.com"
PYTHON_VER="3.11"

# ============ 1. 安装系统依赖 ============
sudo apt update
sudo apt install -y python${PYTHON_VER} python${PYTHON_VER}-venv python3-pip nginx curl git

# ============ 2. 创建项目目录 ============
sudo mkdir -p ${PROJECT_DIR}
sudo chown $USER:$USER ${PROJECT_DIR}
cd ${PROJECT_DIR}

# ============ 3. 克隆/复制代码 ============
# git clone https://github.com/your-username/paper-review-system.git .
# 或复制代码到 ${PROJECT_DIR}

# ============ 4. 后端部署 ============
cd ${PROJECT_DIR}/server
python${PYTHON_VER} -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 创建 .env 文件
cat > ${PROJECT_DIR}/.env << EOF
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=http://127.0.0.1:7000
MODEL_NAME=claude-sonnet-4-5-20251001
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_strong_password
SERVER_PORT=8000
EOF

# ============ 5. 前端部署 ============
cd ${PROJECT_DIR}/client
npm install
npm run build

# ============ 6. Nginx 配置 ============
sudo tee /etc/nginx/sites-available/paper-review > /dev/null << 'NGINX'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    location / {
        root PROJECT_DIR_PLACEHOLDER/client/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 50M;
        proxy_read_timeout 300s;
    }
}
NGINX

sed -i "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" /etc/nginx/sites-available/paper-review
sed -i "s|PROJECT_DIR_PLACEHOLDER|${PROJECT_DIR}|g" /etc/nginx/sites-available/paper-review

sudo ln -sf /etc/nginx/sites-available/paper-review /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# ============ 7. 创建 systemd 服务 ============
sudo tee /etc/systemd/system/paper-review-server.service > /dev/null << 'EOF'
[Unit]
Description=Paper Review Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${PROJECT_DIR}/server
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/server/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable paper-review-server
sudo systemctl start paper-review-server

echo "✅ 部署完成！访问 http://${DOMAIN}"
```

---

## 六、Docker 部署

### 1. 环境要求

- Docker ≥ 20.10
- Docker Compose ≥ 2.0

### 2. 配置 `.env`

编辑项目根目录的 `.env` 文件，**关键配置代理地址**：

```bash
# 方案 A：LiteLLM 代理在宿主机上（推荐）
# 使用 docker-compose 的 host 网络模式时，容器内 127.0.0.1 即宿主机
LAN_MODEL_URL=http://127.0.0.1:7000/v1
LAN_MODEL_API_KEY=sk-your-key
ADMIN_PASSWORD=your_strong_password

# 方案 B：使用 bridge 网络（容器间通过 Docker 网络通信）
# 此时 127.0.0.1 指向容器自身，需改为宿主机 IP
# LAN_MODEL_URL=http://192.168.1.100:7000/v1

# 方案 C：LiteLLM 也在 Docker 容器中运行
# 改为容器名（需在 docker-compose.yml 中定义代理容器）
# LAN_MODEL_URL=http://litellm:7000/v1
```

### 3. 配置管理员认证

生产环境 **必须** 设置 `ADMIN_USERNAME`、`ADMIN_PASSWORD` 和 `JWT_SECRET`：

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_to_a_strong_password
JWT_SECRET=$(openssl rand -hex 32)  # 生成随机密钥
```

> 警告：不设置 `JWT_SECRET` 时，系统会自动生成临时密钥，**容器重启后所有已签发 token 失效**。

### 4. 构建并启动

```bash
# 先构建前端（需要 npm 环境）
cd /path/to/paper-review-system
npm install --prefix client
npm run build --prefix client

# 使用 docker-compose 启动
docker compose up -d --build

# 查看日志
docker compose logs -f backend
docker compose logs -f frontend
```

### 5. 使用 host 网络模式（推荐，最简单）

如果 LiteLLM 代理运行在宿主机上（如通过 systemd 或独立脚本），修改 `docker-compose.yml`：

```yaml
services:
  backend:
    # 取消注释使用 host 网络
    network_mode: host
    ports: []  # host 网络不需要暴露端口
```

然后后端容器可以直接通过 `http://127.0.0.1:7000/v1` 访问宿主机的 LiteLLM 代理。

### 5. 使用 bridge 网络模式

如果需要在 Docker 内部署 LiteLLM 代理，完整的 `docker-compose.yml`：

```yaml
services:
  litellm:
    image: ghcr.io/anthropics/litellm:main-stable
    container_name: litellm-proxy
    restart: unless-stopped
    ports:
      - "7000:7000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: ["--config", "/app/config.yaml", "--port", "7000"]

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: paper-review-backend
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - LAN_MODEL_URL=http://litellm:7000/v1
    depends_on:
      - litellm

  frontend:
    image: nginx:alpine
    container_name: paper-review-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./client/dist:/var/www/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
```

对应的 `litellm_config.yaml`：

```yaml
model_list:
  - model_name: claude-sonnet-4-5-20251001
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20251001
      api_key: sk-your-openai-compatible-key
  - model_name: claude-opus-4-5-20251001
    litellm_params:
      model: anthropic/claude-opus-4-5-20251001
      api_key: sk-your-openai-compatible-key
  - model_name: claude-haiku-4-5-20251001
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: sk-your-openai-compatible-key
```

### 6. 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| "未检测到可用代理" | 容器内 127.0.0.1 不是宿主机 | 改用 host 网络模式，或在 `.env` 中设置宿主机 IP |
| `.env` 未加载 | Docker 容器找不到 `.env` 文件 | 确认 `env_file` 路径正确，或使用 `environment` 直接传值 |
| 后端启动失败 | Python 依赖未安装 | `docker compose logs backend` 查看详细错误 |
| 前端 Nginx 404 | `client/dist` 未构建 | 先 `npm run build` 再 `docker compose up` |

---

## 七、故障排查

| 问题 | 可能原因 | 解决方案 |
|---|---|---|
| 模型下拉列表为空 | LiteLLM 代理未启动或端口不对 | 检查 `http://127.0.0.1:7000/health`，确认代理进程运行 |
| 审稿超时 / Connection error | LLM 代理不可达或模型服务异常 | 查看后端日志，确认 OPENAI_BASE_URL 配置正确 |
| 文件上传失败 | 文件大小超过限制 | 检查 Nginx `client_max_body_size` 和后端超时设置 |
| 审稿结果缺少部分内容 | LLM 某项服务失败 | 查看 "❌ 审稿失败" 提示中的错误信息 |
| Nginx 403 | dist 目录权限 | `sudo chmod -R 755 /path/to/paper-review-system/client/dist` |
| systemd 服务启动失败 | 环境变量未加载 | `journalctl -u paper-review-server -n 50 --no-pager` 查看详细日志 |

---

## 审稿流程

1. **选择模型** — 从下拉列表选择审稿大模型（支持 Claude / GPT / Ollama 等）
2. **上传稿件** — 拖拽或选择论文文件（PDF / DOCX / TXT / Markdown）
3. **自动审稿** — 规则检查 → AI 审阅（语义分析 + 逻辑审查 + 论文润色 + 文献综述） → 生成完整报告
4. **查看结果** — 9 个 Tab 展示：
   - 📊 总评：分数（0-100）+ 优点（≥ 4 条）/ 弱点（≥ 4 条）+ 接收建议
   - 🔍 逻辑审查：研究主题提炼 / 研究路线图与整体框架 / 章节逻辑 / 论点逻辑 / 语句连贯性 / 主题一致性 / 总体评价
   - 🕸️ 知识图谱：提炼稿件知识结构，以网络图可视化展示节点关系
   - 🤖 AI 审阅：逐章节深度意见（每条 ≥ 300 字，含原文定位）
   - ✍️ 修订痕迹：增/删/改对比（≥ 8 条），标注位置和修改理由
   - 📝 自动补全：缺失/不足章节补全草稿
   - ✨ 论文润色：SCI 级语言润色全文
   - 📖 文献综述：基于论文内容的完整文献综述
   - 📚 推荐期刊：Top 10 投稿期刊推荐
5. **下载报告** — 📥 下载 DOCX（含完整批注和推荐期刊）

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | API 信息及文档链接 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/models` | 可用大模型列表（含代理可用性探测） |
| POST | `/api/review` | 上传论文并执行审稿（可选 `model` 参数） |
| GET | `/api/history` | 审稿历史记录 |
| GET | `/api/recommend-journals/{id}` | 获取期刊推荐 |
| GET | `/api/download/{id}` | 下载审稿报告 DOCX |
| GET | `/api/download-original/{id}` | 下载原始稿件 |

---

## 项目结构

```
paper-review-system/
├── server/                          # FastAPI 后端
│   ├── main.py                      # API 入口 & 审稿流程编排
│   ├── models.py                    # 数据模型 (Pydantic)
│   ├── parser.py                    # 论文文本解析 & 章节提取
│   ├── journal_recommender.py       # 期刊推荐引擎（50+ 期刊数据库）
│   ├── storage.py                   # 存储模块
│   ├── requirements.txt             # Python 依赖
│   ├── rule_engine/                 # 规则检查模块
│   │   ├── section_check.py         # 章节完整性检测
│   │   ├── format_check.py          # 格式规范检查
│   │   └── citation_check.py        # 引用匹配检查
│   └── ai_service/                  # AI 审阅服务
│       ├── polisher.py              # 论文逐章润色
│       ├── lit_review.py            # 文献综述生成
│       ├── logical_review_agent.py  # 逻辑审查 Agent
│       └── json_extract.py          # JSON 提取工具
├── client/                          # React 前端
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx                 # 入口
│       ├── App.tsx                  # 主应用（页面路由 + 模型管理）
│       ├── styles.css               # 全局样式
│       ├── types/index.ts           # TypeScript 类型定义
│       ├── hooks/useReview.ts       # 审稿 Hook
│       └── pages/
│           ├── UploadPage.tsx       # 上传页面（含模型选择器）
│           ├── ReviewResultPage.tsx # 审稿结果页（9 Tab + 下载）
│           ├── HistoryPage.tsx      # 历史记录页
│           └── LoginPage.tsx        # 管理员登录页
├── .env                             # 环境变量配置
├── .gitignore
└── README.md
```

---

## 支持的 AI 模型

系统默认提供以下 Claude 4.5 系列模型（通过自定义端点访问）：

- **Claude Sonnet 4.5** — 深度推理，性价比高
- **Claude Opus 4.5** — 最强推理能力
- **Claude Haiku 4.5** — 极速响应

同时支持 Ollama 本地模型自动发现，以及任何 OpenAI Compatible API。

Ollama 服务需在本地运行（默认 `localhost:11434`），系统启动时自动发现可用模型。

自定义模型端点通过 `_CUSTOM_ENDPOINTS` 配置在 `server/main.py` 中。

---

## 推荐期刊数据库

`journal_recommender.py` 内置 50+ 中英文学术期刊/会议，覆盖：

- NLP/AI 顶会：ACL、EMNLP、NeurIPS、ICLR、AAAI 等
- 信息科学/学术出版：Scientometrics、JASIST、Learned Publishing 等
- 计算机应用：Expert Systems with Applications、IP&M、KBS 等
- 中文核心：计算机学报、软件学报、情报学报、图书情报工作 等

每条期刊含影响因子（IF）、接受率、审稿周期、征稿范围等信息，系统根据论文内容匹配度和质量评分智能排序推荐。
